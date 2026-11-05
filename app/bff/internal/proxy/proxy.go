// Package proxy forwards /api/* to the API. It adds the session's bearer token and drops browser credentials.
package proxy

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"net/http/httputil"
	"net/url"
	"path"
	"strings"
	"time"

	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/obs"
)

const (
	// prefix is the path the browser uses. The API itself serves from the root.
	prefix = "/api"
	// maxBodyBytes matches the ingress proxy-body-size of 20m.
	maxBodyBytes = 20 << 20
	// uploadWindow bounds how long a client can take to send its request body.
	uploadWindow = 5 * time.Minute
)

// strippedRequestHeaders are never forwarded. The API trusts only the Authorization header set here.
var strippedRequestHeaders = []string{"Authorization", "Cookie", "Proxy-Authorization", "X-CSRF-Token"}

type tokenKey struct{}

// WithToken makes the access token available to the proxy for this request.
func WithToken(ctx context.Context, token string) context.Context {
	return context.WithValue(ctx, tokenKey{}, token)
}

// Allowed reports whether the browser may reach this path on the API. It is an allowlist, so /metrics, /docs and
// anything added to the API later stay internal until someone decides otherwise.
func Allowed(p string) bool {
	if path.Clean(p) != p {
		return false
	}
	return p == prefix+"/health" || strings.HasPrefix(p, prefix+"/v1/")
}

// New returns the proxy handler. The transport must not buffer, and must not compress, or SSE would stall.
func New(upstream *url.URL, transport http.RoundTripper, m *obs.Metrics, log *slog.Logger) http.Handler {
	rp := &httputil.ReverseProxy{
		Transport: transport,
		// -1 flushes after every write, so an SSE event reaches the browser as soon as the API sends it.
		FlushInterval: -1,
		Rewrite: func(pr *httputil.ProxyRequest) {
			pr.SetURL(upstream)
			pr.Out.URL.Path = strings.TrimPrefix(pr.In.URL.Path, prefix)
			pr.Out.URL.RawPath = strings.TrimPrefix(pr.In.URL.RawPath, prefix)
			pr.SetXForwarded()
			for _, h := range strippedRequestHeaders {
				pr.Out.Header.Del(h)
			}
			if token, ok := pr.In.Context().Value(tokenKey{}).(string); ok && token != "" {
				pr.Out.Header.Set("Authorization", "Bearer "+token)
			}
		},
		ModifyResponse: func(res *http.Response) error {
			// The session cookie is the only cookie this origin needs.
			res.Header.Del("Set-Cookie")
			return nil
		},
		ErrorHandler: func(w http.ResponseWriter, r *http.Request, err error) {
			if errors.Is(err, context.Canceled) {
				// The browser went away, such as a closed stream. That is not an upstream failure.
				w.WriteHeader(499)
				return
			}
			m.UpstreamError.Inc()
			log.ErrorContext(r.Context(), "upstream request failed", "path", r.URL.Path, "error", err.Error())
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadGateway)
			_, _ = w.Write([]byte(`{"detail":"The API is unavailable"}`))
		},
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !Allowed(r.URL.Path) {
			http.NotFound(w, r)
			return
		}
		// The server's WriteTimeout protects short responses and would cut a long stream.
		// Errors only mean the writer has no deadlines to change.
		rc := http.NewResponseController(w)
		_ = rc.SetWriteDeadline(time.Time{})
		_ = rc.SetReadDeadline(time.Now().Add(uploadWindow))
		r.Body = http.MaxBytesReader(w, r.Body, maxBodyBytes)
		rp.ServeHTTP(w, r)
	})
}

// NewTransport is the upstream transport. It is tuned for streaming: no compression, and a long wait for
// the first byte, because the API can take a while before an LLM answer starts.
func NewTransport() http.RoundTripper {
	base, ok := http.DefaultTransport.(*http.Transport)
	if !ok {
		return obs.Transport(http.DefaultTransport)
	}
	t := base.Clone()
	t.Proxy = nil
	t.DisableCompression = true
	t.ResponseHeaderTimeout = uploadWindow
	t.MaxIdleConnsPerHost = 32
	return obs.Transport(t)
}
