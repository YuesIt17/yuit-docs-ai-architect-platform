// Package server wires the public and admin HTTP handlers and their timeouts.
package server

import (
	"context"
	"log/slog"
	"net/http"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promhttp"

	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/auth"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/obs"
)

// Timeouts for the public listener. WriteTimeout applies to /auth/*; the proxy clears it, so streams can run for as
// long as the answer takes.
const (
	ReadHeaderTimeout = 10 * time.Second
	ReadTimeout       = 60 * time.Second
	WriteTimeout      = 60 * time.Second
	IdleTimeout       = 120 * time.Second
)

// PublicHandler serves the browser-facing routes.
func PublicHandler(a *auth.Service, proxy http.Handler, m *obs.Metrics, log *slog.Logger) http.Handler {
	mux := http.NewServeMux()
	route := func(pattern, label string, h http.Handler) {
		mux.Handle(pattern, obs.Instrument(label, m, log, h))
	}
	route("GET /auth/login", "/auth/login", http.HandlerFunc(a.Login))
	route("GET /auth/callback", "/auth/callback", http.HandlerFunc(a.Callback))
	route("GET /auth/me", "/auth/me", http.HandlerFunc(a.Me))
	route("POST /auth/logout", "/auth/logout", http.HandlerFunc(a.Logout))
	// The one API route without a session: the UI needs the auth mode to know that it has to offer a login.
	route("GET /api/v1/auth/mode", "/api/v1/auth/mode", proxy)
	route("/api/", "/api", a.Authenticate(proxy))
	return mux
}

// AdminHandler serves probes and metrics on a separate port that the ingress never routes to.
func AdminHandler(a *auth.Service, ping func(context.Context) error, gatherer prometheus.Gatherer) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		if !a.Ready() || ping(ctx) != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		w.WriteHeader(http.StatusOK)
	})
	mux.Handle("GET /metrics", promhttp.HandlerFor(gatherer, promhttp.HandlerOpts{}))
	return mux
}

// NewPublicServer applies the timeouts.
func NewPublicServer(addr string, h http.Handler) *http.Server {
	return &http.Server{
		Addr:              addr,
		Handler:           h,
		ReadHeaderTimeout: ReadHeaderTimeout,
		ReadTimeout:       ReadTimeout,
		WriteTimeout:      WriteTimeout,
		IdleTimeout:       IdleTimeout,
	}
}

// NewAdminServer serves only short responses, so all its timeouts are tight.
func NewAdminServer(addr string, h http.Handler) *http.Server {
	return &http.Server{
		Addr:              addr,
		Handler:           h,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       5 * time.Second,
		WriteTimeout:      10 * time.Second,
		IdleTimeout:       IdleTimeout,
	}
}
