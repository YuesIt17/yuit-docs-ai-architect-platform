package config

import (
	"encoding/base64"
	"strings"
	"testing"
)

func env(overrides map[string]string) func(string) string {
	base := map[string]string{
		"BFF_PUBLIC_URL":         "https://kp.example",
		"OIDC_ISSUER_URL":        "https://kp.example/idp/realms/kp",
		"OIDC_CLIENT_ID":         "kp-bff",
		"OIDC_CLIENT_SECRET":     "s",
		"SESSION_ENCRYPTION_KEY": base64.StdEncoding.EncodeToString(make([]byte, 32)),
	}
	for k, v := range overrides {
		base[k] = v
	}
	return func(name string) string { return base[name] }
}

func TestDefaults(t *testing.T) {
	cfg, err := Load(env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.DiscoveryURL != cfg.Issuer {
		t.Errorf("discovery = %q", cfg.DiscoveryURL)
	}
	if cfg.Upstream.String() != "http://api:8080" || cfg.ListenAddr != ":8080" || cfg.AdminAddr != ":9090" {
		t.Errorf("cfg = %+v", cfg)
	}
}

func TestPublicURLMustSupportSecureCookies(t *testing.T) {
	cases := map[string]bool{
		"https://kp.example":        true,
		"http://kp.localhost:8088":  true,
		"http://localhost:8088":     true,
		"http://kp.local:8088":      false,
		"http://kp.example":         false,
		"http://localhost.evil.com": false,
		"https://kp.example/app":    false,
		"ftp://kp.example":          false,
	}
	for raw, ok := range cases {
		_, err := Load(env(map[string]string{"BFF_PUBLIC_URL": raw}))
		if (err == nil) != ok {
			t.Errorf("%s: err = %v, want ok = %v", raw, err, ok)
		}
	}
}

func TestMissingSecretsAreAllReported(t *testing.T) {
	_, err := Load(func(string) string { return "" })
	if err == nil {
		t.Fatal("no error")
	}
	for _, name := range []string{"BFF_PUBLIC_URL", "OIDC_ISSUER_URL", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "SESSION_ENCRYPTION_KEY"} {
		if !strings.Contains(err.Error(), name) {
			t.Errorf("error does not name %s: %v", name, err)
		}
	}
}

func TestEncryptionKeyMustBe32Bytes(t *testing.T) {
	short := base64.StdEncoding.EncodeToString(make([]byte, 16))
	for _, key := range []string{short, "not base64!"} {
		_, err := Load(env(map[string]string{"SESSION_ENCRYPTION_KEY": key}))
		if err == nil {
			t.Errorf("accepted %q", key)
		}
	}
}

func TestErrorsDoNotEchoSecrets(t *testing.T) {
	_, err := Load(env(map[string]string{"SESSION_ENCRYPTION_KEY": "super-secret-value"}))
	if err == nil || strings.Contains(err.Error(), "super-secret-value") {
		t.Fatalf("err = %v", err)
	}
}
