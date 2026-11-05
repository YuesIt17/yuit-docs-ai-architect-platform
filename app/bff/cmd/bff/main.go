// Command bff is the backend-for-frontend between the browser, Keycloak and the API.
package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/collectors"
	"github.com/redis/go-redis/v9"

	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/auth"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/config"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/obs"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/proxy"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/server"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/session"
)

// shutdownGrace is how long open streams get to finish after SIGTERM.
const shutdownGrace = 25 * time.Second

func main() {
	if err := run(); err != nil {
		obs.NewLogger(os.Stderr, "INFO").Error("bff stopped", "error", err.Error())
		os.Exit(1)
	}
}

func run() error {
	cfg, err := config.Load(os.Getenv)
	if err != nil {
		return err
	}
	log := obs.NewLogger(os.Stdout, cfg.LogLevel)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	shutdownTracing, err := obs.InitTracing(ctx, log)
	if err != nil {
		return err
	}

	redisOptions, err := redis.ParseURL(cfg.RedisURL)
	if err != nil {
		return errors.New("REDIS_URL is not a valid redis URL")
	}
	rdb := redis.NewClient(redisOptions)
	defer func() { _ = rdb.Close() }()

	store, err := session.NewStore(rdb, cfg.EncryptionKey, cfg.SessionTTL)
	if err != nil {
		return err
	}

	registry := prometheus.NewRegistry()
	registry.MustRegister(collectors.NewGoCollector(), collectors.NewProcessCollector(collectors.ProcessCollectorOpts{}))
	metrics := obs.NewMetrics(registry)

	transport := proxy.NewTransport()
	authService, err := auth.New(auth.Options{
		PublicURL:    cfg.PublicURL,
		Issuer:       cfg.Issuer,
		DiscoveryURL: cfg.DiscoveryURL,
		ClientID:     cfg.ClientID,
		ClientSecret: cfg.ClientSecret,
		Scopes:       cfg.Scopes,
		APIURL:       cfg.Upstream,
		HTTPClient:   &http.Client{Transport: transport, Timeout: 10 * time.Second},
		Store:        store,
		Metrics:      metrics,
		Logger:       log,
	})
	if err != nil {
		return err
	}
	go authService.ConnectUntilReady(ctx)

	public := server.NewPublicServer(cfg.ListenAddr, server.PublicHandler(
		authService, proxy.New(cfg.Upstream, transport, metrics, log), metrics, log))
	admin := server.NewAdminServer(cfg.AdminAddr, server.AdminHandler(
		authService, func(c context.Context) error { return rdb.Ping(c).Err() }, registry))

	serveErr := make(chan error, 2)
	for _, srv := range []*http.Server{public, admin} {
		go func() {
			if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
				serveErr <- err
			}
		}()
	}
	log.InfoContext(ctx, "bff started", "listen", cfg.ListenAddr, "admin", cfg.AdminAddr)

	select {
	case err := <-serveErr:
		return err
	case <-ctx.Done():
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), shutdownGrace)
	defer cancel()
	log.InfoContext(shutdownCtx, "bff stopping")
	return errors.Join(public.Shutdown(shutdownCtx), admin.Shutdown(shutdownCtx), shutdownTracing(shutdownCtx))
}
