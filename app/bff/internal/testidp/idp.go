// Package testidp is a small OIDC provider for tests. It enforces what Keycloak enforces in the flows the BFF uses:
// PKCE on the code exchange, client authentication, and refresh token rotation with reuse detection.
package testidp

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	jose "github.com/go-jose/go-jose/v4"
	"github.com/go-jose/go-jose/v4/jwt"
)

const (
	// ClientID is the client the BFF under test must present.
	ClientID = "kp-bff"
	// ClientSecret is the secret the BFF under test must present.
	ClientSecret = "test-secret"
	// Subject is the user every login signs in as.
	Subject = "user-sub-1"
)

type authCode struct {
	challenge, redirectURI, nonce string
}

// IDP is the provider. The exported fields change its behavior between test steps.
type IDP struct {
	Server *httptest.Server

	// AccessTTL is the lifetime of issued access tokens.
	AccessTTL time.Duration
	// RefreshDelay widens the window for concurrent refresh attempts.
	RefreshDelay time.Duration
	// NonceOverride replaces the nonce in ID tokens, to simulate an injected token.
	NonceOverride string
	// RefreshDown makes the token endpoint fail with a 500 on refresh.
	RefreshDown atomic.Bool

	// RefreshCalls counts refresh requests that reached the token endpoint.
	RefreshCalls atomic.Int64
	// ReuseDetected counts refresh tokens redeemed more than once.
	ReuseDetected atomic.Int64
	// LoggedOut counts sessions ended through the logout endpoint.
	LoggedOut atomic.Int64

	key    *rsa.PrivateKey
	signer jose.Signer

	mu      sync.Mutex
	codes   map[string]authCode
	refresh map[string]bool // refresh token -> still valid
	nonce   map[string]string
}

// New starts a provider that stops when the test ends.
func New(t testing.TB) *IDP {
	t.Helper()
	key, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatal(err)
	}
	signer, err := jose.NewSigner(
		jose.SigningKey{Algorithm: jose.RS256, Key: jose.JSONWebKey{Key: key, KeyID: "k1"}},
		(&jose.SignerOptions{}).WithType("JWT"))
	if err != nil {
		t.Fatal(err)
	}
	idp := &IDP{
		AccessTTL: 5 * time.Minute,
		key:       key,
		signer:    signer,
		codes:     map[string]authCode{},
		refresh:   map[string]bool{},
		nonce:     map[string]string{},
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /.well-known/openid-configuration", idp.discovery)
	mux.HandleFunc("GET /jwks", idp.jwks)
	mux.HandleFunc("GET /authorize", idp.authorize)
	mux.HandleFunc("POST /token", idp.token)
	mux.HandleFunc("POST /logout", idp.logout)
	idp.Server = httptest.NewServer(mux)
	t.Cleanup(idp.Server.Close)
	return idp
}

// Issuer is the provider's issuer URL.
func (i *IDP) Issuer() string { return i.Server.URL }

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func (i *IDP) discovery(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"issuer":                                i.Issuer(),
		"authorization_endpoint":                i.Issuer() + "/authorize",
		"token_endpoint":                        i.Issuer() + "/token",
		"jwks_uri":                              i.Issuer() + "/jwks",
		"id_token_signing_alg_values_supported": []string{"RS256"},
	})
}

func (i *IDP) jwks(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, http.StatusOK, jose.JSONWebKeySet{Keys: []jose.JSONWebKey{
		{Key: i.key.Public(), KeyID: "k1", Algorithm: "RS256", Use: "sig"},
	}})
}

// authorize signs the user in at once and redirects back, as Keycloak does after its login form.
func (i *IDP) authorize(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	if q.Get("code_challenge_method") != "S256" || q.Get("code_challenge") == "" ||
		q.Get("state") == "" || q.Get("nonce") == "" || q.Get("response_type") != "code" {
		http.Error(w, "bad authorization request", http.StatusBadRequest)
		return
	}
	code := rand.Text()
	i.mu.Lock()
	i.codes[code] = authCode{q.Get("code_challenge"), q.Get("redirect_uri"), q.Get("nonce")}
	i.mu.Unlock()
	target, err := url.Parse(q.Get("redirect_uri"))
	if err != nil {
		http.Error(w, "bad redirect_uri", http.StatusBadRequest)
		return
	}
	v := target.Query()
	v.Set("code", code)
	v.Set("state", q.Get("state"))
	target.RawQuery = v.Encode()
	http.Redirect(w, r, target.String(), http.StatusFound)
}

func tokenError(w http.ResponseWriter, status int, code string) {
	writeJSON(w, status, map[string]string{"error": code})
}

func (i *IDP) token(w http.ResponseWriter, r *http.Request) {
	if r.FormValue("client_id") != ClientID || r.FormValue("client_secret") != ClientSecret {
		tokenError(w, http.StatusUnauthorized, "invalid_client")
		return
	}
	switch r.FormValue("grant_type") {
	case "authorization_code":
		i.exchange(w, r)
	case "refresh_token":
		i.rotate(w, r)
	default:
		tokenError(w, http.StatusBadRequest, "unsupported_grant_type")
	}
}

func (i *IDP) exchange(w http.ResponseWriter, r *http.Request) {
	i.mu.Lock()
	code, ok := i.codes[r.FormValue("code")]
	delete(i.codes, r.FormValue("code"))
	i.mu.Unlock()
	sum := sha256.Sum256([]byte(r.FormValue("code_verifier")))
	if !ok || base64.RawURLEncoding.EncodeToString(sum[:]) != code.challenge || r.FormValue("redirect_uri") != code.redirectURI {
		tokenError(w, http.StatusBadRequest, "invalid_grant")
		return
	}
	nonce := code.nonce
	if i.NonceOverride != "" {
		nonce = i.NonceOverride
	}
	i.issue(w, nonce)
}

func (i *IDP) rotate(w http.ResponseWriter, r *http.Request) {
	i.RefreshCalls.Add(1)
	if i.RefreshDelay > 0 {
		time.Sleep(i.RefreshDelay)
	}
	if i.RefreshDown.Load() {
		tokenError(w, http.StatusInternalServerError, "server_error")
		return
	}
	presented := r.FormValue("refresh_token")
	i.mu.Lock()
	valid, known := i.refresh[presented]
	if known {
		i.refresh[presented] = false
	}
	nonce := i.nonce[presented]
	i.mu.Unlock()
	if !known || !valid {
		if known {
			i.ReuseDetected.Add(1)
		}
		tokenError(w, http.StatusBadRequest, "invalid_grant")
		return
	}
	i.issue(w, nonce)
}

// Revoke ends all refresh tokens, as an expired or administratively killed IdP session would.
func (i *IDP) Revoke() {
	i.mu.Lock()
	defer i.mu.Unlock()
	for token := range i.refresh {
		i.refresh[token] = false
	}
}

func (i *IDP) issue(w http.ResponseWriter, nonce string) {
	now := time.Now()
	type idClaims struct {
		jwt.Claims
		Nonce    string `json:"nonce"`
		Username string `json:"preferred_username"`
	}
	idToken, err := jwt.Signed(i.signer).Claims(idClaims{
		Claims: jwt.Claims{
			Issuer:   i.Issuer(),
			Subject:  Subject,
			Audience: jwt.Audience{ClientID},
			IssuedAt: jwt.NewNumericDate(now),
			Expiry:   jwt.NewNumericDate(now.Add(5 * time.Minute)),
		},
		Nonce:    nonce,
		Username: "manager",
	}).Serialize()
	if err != nil {
		tokenError(w, http.StatusInternalServerError, "server_error")
		return
	}
	refresh := "refresh-" + rand.Text()
	i.mu.Lock()
	i.refresh[refresh] = true
	i.nonce[refresh] = nonce
	i.mu.Unlock()
	writeJSON(w, http.StatusOK, map[string]any{
		"access_token":  "access-" + rand.Text(),
		"refresh_token": refresh,
		"id_token":      idToken,
		"token_type":    "Bearer",
		"expires_in":    int(i.AccessTTL.Seconds()),
	})
}

func (i *IDP) logout(w http.ResponseWriter, r *http.Request) {
	if r.FormValue("client_id") != ClientID || r.FormValue("client_secret") != ClientSecret {
		tokenError(w, http.StatusUnauthorized, "invalid_client")
		return
	}
	i.mu.Lock()
	valid := i.refresh[r.FormValue("refresh_token")]
	i.refresh[r.FormValue("refresh_token")] = false
	i.mu.Unlock()
	if !valid {
		tokenError(w, http.StatusBadRequest, "invalid_grant")
		return
	}
	i.LoggedOut.Add(1)
	w.WriteHeader(http.StatusNoContent)
}
