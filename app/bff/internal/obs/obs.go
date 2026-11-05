// Package obs provides the logs, metrics and traces, in the shapes the existing LGTM stack already reads.
package obs

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
)

// ServiceName is the name used in logs and traces.
const ServiceName = "kp-bff"

// traceHandler adds trace_id, the field Loki uses to link a log line to its Tempo trace.
type traceHandler struct{ slog.Handler }

func (h traceHandler) Handle(ctx context.Context, r slog.Record) error {
	if sc := trace.SpanContextFromContext(ctx); sc.HasTraceID() {
		r.AddAttrs(slog.String("trace_id", sc.TraceID().String()))
	}
	return h.Handler.Handle(ctx, r)
}

func (h traceHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return traceHandler{h.Handler.WithAttrs(attrs)}
}

func (h traceHandler) WithGroup(name string) slog.Handler {
	return traceHandler{h.Handler.WithGroup(name)}
}

// NewLogger writes one JSON object per line with the same field names as the API's formatter.
func NewLogger(w io.Writer, level string) *slog.Logger {
	var lvl slog.Level
	if err := lvl.UnmarshalText([]byte(level)); err != nil {
		lvl = slog.LevelInfo
	}
	base := slog.NewJSONHandler(w, &slog.HandlerOptions{
		Level: lvl,
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			if len(groups) > 0 {
				return a
			}
			switch a.Key {
			case slog.TimeKey:
				a.Key = "ts"
			case slog.LevelKey:
				a.Value = slog.StringValue(strings.ToLower(a.Value.String()))
			}
			return a
		},
	})
	return slog.New(traceHandler{base}).With("service", ServiceName, "logger", "bff")
}

// Metrics are the BFF's Prometheus series. Route labels are fixed patterns, so cardinality stays bounded.
type Metrics struct {
	Requests      *prometheus.CounterVec
	Duration      *prometheus.HistogramVec
	InFlight      prometheus.Gauge
	TokenRefresh  *prometheus.CounterVec
	Logins        *prometheus.CounterVec
	Logouts       *prometheus.CounterVec
	CSRFRejected  prometheus.Counter
	UpstreamError prometheus.Counter
}

// NewMetrics registers all series on reg.
func NewMetrics(reg prometheus.Registerer) *Metrics {
	m := &Metrics{
		Requests: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "bff_http_requests_total", Help: "Requests by route, method and status code.",
		}, []string{"route", "method", "code"}),
		Duration: prometheus.NewHistogramVec(prometheus.HistogramOpts{
			Name:    "bff_http_request_duration_seconds",
			Help:    "Time until the response finished. Streams count their full length.",
			Buckets: []float64{0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 300},
		}, []string{"route"}),
		InFlight: prometheus.NewGauge(prometheus.GaugeOpts{
			Name: "bff_http_requests_in_flight", Help: "Requests being served, including open streams.",
		}),
		TokenRefresh: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "bff_token_refresh_total", Help: "Refresh attempts by result.",
		}, []string{"result"}),
		Logins: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "bff_logins_total", Help: "Finished logins by result.",
		}, []string{"result"}),
		Logouts: prometheus.NewCounterVec(prometheus.CounterOpts{
			Name: "bff_logouts_total", Help: "Logouts by whether the IdP session was ended.",
		}, []string{"idp_session"}),
		CSRFRejected: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "bff_csrf_rejected_total", Help: "State-changing requests rejected by CSRF checks.",
		}),
		UpstreamError: prometheus.NewCounter(prometheus.CounterOpts{
			Name: "bff_upstream_errors_total", Help: "Requests the API did not answer.",
		}),
	}
	reg.MustRegister(m.Requests, m.Duration, m.InFlight, m.TokenRefresh, m.Logins, m.Logouts, m.CSRFRejected, m.UpstreamError)
	return m
}

// statusRecorder notes the status code. Unwrap keeps http.ResponseController working, which streaming relies on.
type statusRecorder struct {
	http.ResponseWriter
	code int
}

func (s *statusRecorder) WriteHeader(code int) {
	if s.code == 0 {
		s.code = code
	}
	s.ResponseWriter.WriteHeader(code)
}

func (s *statusRecorder) Write(b []byte) (int, error) {
	if s.code == 0 {
		s.code = http.StatusOK
	}
	return s.ResponseWriter.Write(b)
}

func (s *statusRecorder) Unwrap() http.ResponseWriter { return s.ResponseWriter }

// Instrument wraps a route with a span, metrics and one log line. It logs the path but not the query,
// because /auth/callback carries the authorization code there.
func Instrument(route string, m *Metrics, log *slog.Logger, next http.Handler) http.Handler {
	inner := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		rec := &statusRecorder{ResponseWriter: w}
		m.InFlight.Inc()
		defer func() {
			m.InFlight.Dec()
			code := rec.code
			if code == 0 {
				code = http.StatusOK
			}
			elapsed := time.Since(start)
			m.Requests.WithLabelValues(route, r.Method, strconv.Itoa(code)).Inc()
			m.Duration.WithLabelValues(route).Observe(elapsed.Seconds())
			log.InfoContext(r.Context(), "request",
				"method", r.Method, "route", route, "path", r.URL.Path,
				"status", code, "duration_ms", elapsed.Milliseconds())
		}()
		next.ServeHTTP(rec, r)
	})
	return otelhttp.NewHandler(inner, route)
}

// InitTracing exports spans over OTLP/HTTP. It reads the standard OTEL_EXPORTER_OTLP_ENDPOINT variable, and
// OTEL_SDK_DISABLED=true turns it off. The returned function flushes pending spans.
func InitTracing(ctx context.Context) (func(context.Context) error, error) {
	otel.SetTextMapPropagator(propagation.TraceContext{})
	if strings.EqualFold(os.Getenv("OTEL_SDK_DISABLED"), "true") {
		return func(context.Context) error { return nil }, nil
	}
	exporter, err := otlptracehttp.New(ctx)
	if err != nil {
		return nil, fmt.Errorf("obs: exporter: %w", err)
	}
	provider := sdktrace.NewTracerProvider(
		sdktrace.WithBatcher(exporter),
		sdktrace.WithResource(resource.NewSchemaless(semconv.ServiceName(ServiceName))),
	)
	otel.SetTracerProvider(provider)
	return provider.Shutdown, nil
}

// Transport traces outgoing requests and propagates the trace to the API and the IdP.
func Transport(base http.RoundTripper) http.RoundTripper {
	return otelhttp.NewTransport(base)
}
