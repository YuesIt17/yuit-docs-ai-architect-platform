// Package config loads and validates the BFF settings from the environment.
package config

import (
	"encoding/base64"
	"errors"
	"fmt"
	"net/url"
	"strings"
	"time"
)

// Config holds validated settings. It contains secrets, so it must never be logged.
type Config struct {
	PublicURL     string
	Issuer        string
	DiscoveryURL  string
	ClientID      string
	ClientSecret  string
	Scopes        []string
	Upstream      *url.URL
	RedisURL      string
	EncryptionKey []byte
	SessionTTL    time.Duration
	ListenAddr    string
	AdminAddr     string
	LogLevel      string
}

// Load reads settings through getenv, so tests need no process environment.
func Load(getenv func(string) string) (*Config, error) {
	var errs []error
	require := func(name string) string {
		v := getenv(name)
		if v == "" {
			errs = append(errs, fmt.Errorf("%s is required", name))
		}
		return v
	}
	orDefault := func(name, fallback string) string {
		if v := getenv(name); v != "" {
			return v
		}
		return fallback
	}

	cfg := &Config{
		PublicURL:    strings.TrimRight(require("BFF_PUBLIC_URL"), "/"),
		Issuer:       require("OIDC_ISSUER_URL"),
		DiscoveryURL: getenv("OIDC_DISCOVERY_URL"),
		ClientID:     require("OIDC_CLIENT_ID"),
		ClientSecret: require("OIDC_CLIENT_SECRET"),
		Scopes:       strings.Fields(orDefault("OIDC_SCOPES", "openid profile")),
		RedisURL:     orDefault("REDIS_URL", "redis://redis:6379/1"),
		ListenAddr:   orDefault("BFF_LISTEN_ADDR", ":8080"),
		AdminAddr:    orDefault("BFF_ADMIN_ADDR", ":9090"),
		LogLevel:     orDefault("LOG_LEVEL", "INFO"),
	}
	if cfg.DiscoveryURL == "" {
		cfg.DiscoveryURL = cfg.Issuer
	}

	if cfg.PublicURL != "" {
		if err := checkCookieCapableOrigin(cfg.PublicURL); err != nil {
			errs = append(errs, fmt.Errorf("BFF_PUBLIC_URL: %w", err))
		}
	}

	upstream, err := url.Parse(orDefault("API_UPSTREAM_URL", "http://api:8080"))
	if err != nil || upstream.Host == "" {
		errs = append(errs, errors.New("API_UPSTREAM_URL must be an absolute URL"))
	}
	cfg.Upstream = upstream

	key, err := base64.StdEncoding.DecodeString(require("SESSION_ENCRYPTION_KEY"))
	if err != nil || len(key) != 32 {
		errs = append(errs, errors.New("SESSION_ENCRYPTION_KEY must be 32 bytes in standard base64"))
	}
	cfg.EncryptionKey = key

	cfg.SessionTTL, err = time.ParseDuration(orDefault("SESSION_TTL", "8h"))
	if err != nil || cfg.SessionTTL <= 0 {
		errs = append(errs, errors.New("SESSION_TTL must be a positive duration"))
	}

	if err := errors.Join(errs...); err != nil {
		return nil, err
	}
	return cfg, nil
}

// checkCookieCapableOrigin rejects origins where the browser would drop the session cookie.
// The cookie is always Secure with the __Host- prefix. Browsers accept that over HTTPS, and Chromium
// also over plain HTTP on *.localhost, which it treats as trustworthy. Any other plain-HTTP host would
// cause a silent login loop, so it fails at startup instead of getting a weaker cookie.
func checkCookieCapableOrigin(raw string) error {
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" {
		return errors.New("must be an absolute URL")
	}
	if u.Path != "" || u.RawQuery != "" || u.Fragment != "" {
		return errors.New("must be an origin, with no path")
	}
	switch u.Scheme {
	case "https":
		return nil
	case "http":
		host := u.Hostname()
		if host == "localhost" || strings.HasSuffix(host, ".localhost") {
			return nil
		}
		return errors.New("plain HTTP is only allowed on localhost or *.localhost, because Secure cookies need it")
	default:
		return errors.New("scheme must be http or https")
	}
}
