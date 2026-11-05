// Package auth implements the OIDC login, the session cookie, CSRF checks and token refresh.
//
// All protocol and token work is delegated to golang.org/x/oauth2 and github.com/coreos/go-oidc.
package auth

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"net/url"
	"strings"
	"sync/atomic"
	"time"

	"github.com/coreos/go-oidc/v3/oidc"
	"golang.org/x/oauth2"
	"golang.org/x/sync/singleflight"

	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/obs"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/proxy"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/session"
)

const (
	// SessionCookie holds only an opaque id. __Host- forces Secure, Path=/ and no Domain.
	SessionCookie = "__Host-kp_session"
	// loginCookie binds an authorization request to the browser that started it, which stops login CSRF.
	loginCookie = "__Host-kp_login"
	// CSRFHeader carries the token returned by /auth/me on state-changing requests.
	CSRFHeader = "X-CSRF-Token"

	loginCookieMaxAge = 600
	// refreshSkew renews a token early, so it cannot expire between this check and the API's own.
	refreshSkew = 30 * time.Second
	// refreshTimeout must exceed lockTTL, so a waiter can take over from a replica that died holding the lock.
	refreshTimeout = 20 * time.Second
	lockTTL        = 15 * time.Second
	lockPoll       = 100 * time.Millisecond
)

// Errors returned while getting a usable access token.
var (
	// ErrSessionEnded means the browser must log in again.
	ErrSessionEnded = errors.New("auth: session ended")
	// ErrIDPUnavailable means the session is intact but the token cannot be renewed right now.
	ErrIDPUnavailable = errors.New("auth: identity provider unavailable")
)

// Options configures a Service.
type Options struct {
	PublicURL    string
	Issuer       string
	DiscoveryURL string
	ClientID     string
	ClientSecret string
	Scopes       []string
	// APIURL is where /auth/me asks who the token belongs to.
	APIURL *url.URL
	// HTTPClient is used for the IdP and for the API lookup.
	HTTPClient *http.Client
	Store      *session.Store
	Metrics    *obs.Metrics
	Logger     *slog.Logger
}

type oidcClient struct {
	oauth     *oauth2.Config
	verifier  *oidc.IDTokenVerifier
	logoutURL string
}

// Service holds the auth handlers. It is safe for concurrent use.
type Service struct {
	opt     Options
	client  atomic.Pointer[oidcClient]
	refresh singleflight.Group
	origin  *http.CrossOriginProtection
}

// New returns a Service. Call Connect before it can serve logins.
func New(opt Options) (*Service, error) {
	origin := http.NewCrossOriginProtection()
	if err := origin.AddTrustedOrigin(opt.PublicURL); err != nil {
		return nil, fmt.Errorf("auth: trusted origin: %w", err)
	}
	return &Service{opt: opt, origin: origin}, nil
}

func (s *Service) oauthContext(ctx context.Context) context.Context {
	return context.WithValue(ctx, oauth2.HTTPClient, s.opt.HTTPClient)
}

// Connect fetches the IdP's metadata.
//
// The issuer in tokens is the URL the browser sees, which may not resolve inside the cluster. So discovery can use an
// internal URL. go-oidc still pins the expected issuer, and this function also requires the metadata to agree with it.
func (s *Service) Connect(ctx context.Context) error {
	ctx = oidc.ClientContext(ctx, s.opt.HTTPClient)
	if s.opt.DiscoveryURL != s.opt.Issuer {
		ctx = oidc.InsecureIssuerURLContext(ctx, s.opt.Issuer)
	}
	provider, err := oidc.NewProvider(ctx, s.opt.DiscoveryURL)
	if err != nil {
		return fmt.Errorf("auth: discovery: %w", err)
	}
	var metadata struct {
		Issuer string `json:"issuer"`
	}
	if err := provider.Claims(&metadata); err != nil {
		return fmt.Errorf("auth: metadata: %w", err)
	}
	if metadata.Issuer != s.opt.Issuer {
		return fmt.Errorf("auth: metadata names issuer %q, expected %q", metadata.Issuer, s.opt.Issuer)
	}

	endpoint := provider.Endpoint()
	endpoint.AuthStyle = oauth2.AuthStyleInParams
	s.client.Store(&oidcClient{
		oauth: &oauth2.Config{
			ClientID:     s.opt.ClientID,
			ClientSecret: s.opt.ClientSecret,
			Endpoint:     endpoint,
			RedirectURL:  s.opt.PublicURL + "/auth/callback",
			Scopes:       s.opt.Scopes,
		},
		verifier: provider.Verifier(&oidc.Config{ClientID: s.opt.ClientID, SupportedSigningAlgs: []string{oidc.RS256}}),
		// Keycloak's logout endpoint sits beside the token endpoint, which discovery gives as an internal URL.
		// The advertised end_session_endpoint is browser-facing and would need the ID token in the browser's URL.
		logoutURL: strings.TrimSuffix(endpoint.TokenURL, "/token") + "/logout",
	})
	return nil
}

// ConnectUntilReady retries Connect, because the IdP often starts after the BFF.
func (s *Service) ConnectUntilReady(ctx context.Context) {
	for {
		err := s.Connect(ctx)
		if err == nil {
			s.opt.Logger.InfoContext(ctx, "identity provider connected")
			return
		}
		s.opt.Logger.WarnContext(ctx, "identity provider not ready", "error", err.Error())
		select {
		case <-ctx.Done():
			return
		case <-time.After(5 * time.Second):
		}
	}
}

// Ready reports whether the IdP's metadata has been loaded.
func (s *Service) Ready() bool { return s.client.Load() != nil }

func setCookie(w http.ResponseWriter, name, value string, maxAge int) {
	http.SetCookie(w, &http.Cookie{
		Name:     name,
		Value:    value,
		Path:     "/",
		MaxAge:   maxAge,
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteLaxMode,
	})
}

func writeJSON(w http.ResponseWriter, status int, body any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}

func writeError(w http.ResponseWriter, status int, detail string) {
	writeJSON(w, status, map[string]string{"detail": detail})
}

// safeReturnPath accepts only same-origin paths, so /auth/login cannot be used as an open redirect.
func safeReturnPath(p string) string {
	if !strings.HasPrefix(p, "/") || strings.HasPrefix(p, "//") || strings.ContainsAny(p, "\\\r\n") {
		return "/"
	}
	return p
}

// Login starts Authorization Code with PKCE, state and nonce.
func (s *Service) Login(w http.ResponseWriter, r *http.Request) {
	client := s.client.Load()
	if client == nil {
		writeError(w, http.StatusServiceUnavailable, "The identity provider is not ready")
		return
	}
	state, nonce, verifier := rand.Text(), rand.Text(), oauth2.GenerateVerifier()
	login := &session.Login{Verifier: verifier, Nonce: nonce, ReturnTo: safeReturnPath(r.URL.Query().Get("return_to"))}
	if err := s.opt.Store.SaveLogin(r.Context(), state, login); err != nil {
		s.opt.Logger.ErrorContext(r.Context(), "saving login state failed", "error", err.Error())
		writeError(w, http.StatusServiceUnavailable, "Login is temporarily unavailable")
		return
	}
	setCookie(w, loginCookie, state, loginCookieMaxAge)
	w.Header().Set("Cache-Control", "no-store")
	target := client.oauth.AuthCodeURL(state, oauth2.S256ChallengeOption(verifier), oidc.Nonce(nonce))
	http.Redirect(w, r, target, http.StatusFound)
}

// failLogin sends the browser back to the UI with a fixed code, never with text from the request.
func (s *Service) failLogin(w http.ResponseWriter, r *http.Request, code string) {
	s.opt.Metrics.Logins.WithLabelValues(code).Inc()
	s.opt.Logger.WarnContext(r.Context(), "login failed", "reason", code)
	http.Redirect(w, r, "/?login_error="+code, http.StatusFound)
}

// Callback finishes the login. It checks state against the browser's cookie, redeems the code with the PKCE verifier,
// verifies the ID token and its nonce, and only then creates a new session.
func (s *Service) Callback(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	w.Header().Set("Cache-Control", "no-store")
	client := s.client.Load()
	if client == nil {
		writeError(w, http.StatusServiceUnavailable, "The identity provider is not ready")
		return
	}
	query := r.URL.Query()
	state := query.Get("state")
	cookie, err := r.Cookie(loginCookie)
	setCookie(w, loginCookie, "", -1)
	if err != nil || state == "" || subtle.ConstantTimeCompare([]byte(cookie.Value), []byte(state)) != 1 {
		s.failLogin(w, r, "invalid_state")
		return
	}
	login, err := s.opt.Store.TakeLogin(ctx, state)
	if err != nil {
		s.failLogin(w, r, "invalid_state")
		return
	}
	if query.Get("error") != "" {
		s.failLogin(w, r, "idp_denied")
		return
	}

	oauthCtx := s.oauthContext(ctx)
	token, err := client.oauth.Exchange(oauthCtx, query.Get("code"), oauth2.VerifierOption(login.Verifier))
	if err != nil {
		s.opt.Logger.ErrorContext(ctx, "code exchange failed", "error", safeOAuthError(err))
		s.failLogin(w, r, "exchange_failed")
		return
	}
	rawID, _ := token.Extra("id_token").(string)
	idToken, err := client.verifier.Verify(oauthCtx, rawID)
	if err != nil {
		s.failLogin(w, r, "invalid_id_token")
		return
	}
	if subtle.ConstantTimeCompare([]byte(idToken.Nonce), []byte(login.Nonce)) != 1 {
		s.failLogin(w, r, "invalid_nonce")
		return
	}
	var claims struct {
		PreferredUsername string `json:"preferred_username"`
	}
	if err := idToken.Claims(&claims); err != nil {
		s.failLogin(w, r, "invalid_id_token")
		return
	}

	// A login always gets a new id, so a session id planted before login is worthless afterwards.
	if old, err := r.Cookie(SessionCookie); err == nil {
		if err := s.opt.Store.Delete(ctx, old.Value); err != nil {
			s.opt.Logger.WarnContext(ctx, "deleting the previous session failed", "error", err.Error())
		}
	}
	id := session.NewID()
	sess := &session.Session{
		Subject:      idToken.Subject,
		Username:     claims.PreferredUsername,
		AccessToken:  token.AccessToken,
		RefreshToken: token.RefreshToken,
		AccessExpiry: token.Expiry,
		CSRFToken:    rand.Text(),
	}
	if err := s.opt.Store.Create(ctx, id, sess); err != nil {
		s.opt.Logger.ErrorContext(ctx, "saving session failed", "error", err.Error())
		s.failLogin(w, r, "session_unavailable")
		return
	}
	setCookie(w, SessionCookie, id, 0)
	s.opt.Metrics.Logins.WithLabelValues("success").Inc()
	http.Redirect(w, r, login.ReturnTo, http.StatusFound) //nolint:gosec // Login stored it through safeReturnPath, and the record is authenticated.
}

// safeOAuthError describes an OAuth failure without echoing the IdP's response body, which could contain token data.
func safeOAuthError(err error) string {
	var re *oauth2.RetrieveError
	if errors.As(err, &re) {
		return "token endpoint returned " + re.ErrorCode
	}
	return "token endpoint unreachable"
}

func sessionID(r *http.Request) string {
	cookie, err := r.Cookie(SessionCookie)
	if err != nil {
		return ""
	}
	return cookie.Value
}

// validCSRF combines the stdlib cross-origin check (Sec-Fetch-Site, then Origin) with a token bound to the session.
func (s *Service) validCSRF(r *http.Request, sess *session.Session) bool {
	if s.origin.Check(r) != nil {
		return false
	}
	sent := r.Header.Get(CSRFHeader)
	return sent != "" && subtle.ConstantTimeCompare([]byte(sent), []byte(sess.CSRFToken)) == 1
}

func unsafeMethod(method string) bool {
	switch method {
	case http.MethodGet, http.MethodHead, http.MethodOptions:
		return false
	default:
		return true
	}
}

// writeSessionError turns a failure of freshSession into a response. A dead session also loses its cookie.
func (s *Service) writeSessionError(w http.ResponseWriter, r *http.Request, err error) {
	switch {
	case errors.Is(err, session.ErrNotFound), errors.Is(err, ErrSessionEnded):
		setCookie(w, SessionCookie, "", -1)
		writeError(w, http.StatusUnauthorized, "Not signed in")
	case errors.Is(err, ErrIDPUnavailable):
		writeError(w, http.StatusServiceUnavailable, "The identity provider is unavailable")
	default:
		s.opt.Logger.ErrorContext(r.Context(), "session lookup failed", "error", err.Error())
		writeError(w, http.StatusServiceUnavailable, "Sessions are temporarily unavailable")
	}
}

// Authenticate requires a session and a CSRF token on state-changing methods, then hands the token to the proxy.
func (s *Service) Authenticate(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := sessionID(r)
		if id == "" {
			writeError(w, http.StatusUnauthorized, "Not signed in")
			return
		}
		sess, err := s.freshSession(r.Context(), id)
		if err != nil {
			s.writeSessionError(w, r, err)
			return
		}
		if unsafeMethod(r.Method) && !s.validCSRF(r, sess) {
			s.opt.Metrics.CSRFRejected.Inc()
			writeError(w, http.StatusForbidden, "CSRF check failed")
			return
		}
		next.ServeHTTP(w, r.WithContext(proxy.WithToken(r.Context(), sess.AccessToken)))
	})
}

// freshSession returns the session with a usable access token, refreshing it if needed.
func (s *Service) freshSession(ctx context.Context, id string) (*session.Session, error) {
	sess, err := s.opt.Store.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if time.Until(sess.AccessExpiry) > refreshSkew {
		return sess, nil
	}
	// One request per process does the refresh and the others share its result. It keeps running if the request that
	// started it is cancelled, because the IdP may already have rotated the refresh token.
	ch := s.refresh.DoChan(id, func() (any, error) {
		refreshCtx, cancel := context.WithTimeout(context.WithoutCancel(ctx), refreshTimeout)
		defer cancel()
		return s.refreshAcrossReplicas(refreshCtx, id)
	})
	select {
	case res := <-ch:
		if res.Err != nil {
			return nil, res.Err
		}
		fresh, ok := res.Val.(*session.Session)
		if !ok {
			return nil, errors.New("auth: unexpected refresh result")
		}
		return fresh, nil
	case <-ctx.Done():
		return nil, fmt.Errorf("auth: waiting for refresh: %w", ctx.Err())
	}
}

// refreshAcrossReplicas uses a Redis lock so that only one replica redeems a refresh token. A loser polls until the
// winner has stored the new token, and takes over if the winner dies and the lock expires.
func (s *Service) refreshAcrossReplicas(ctx context.Context, id string) (*session.Session, error) {
	for {
		unlock, acquired, err := s.opt.Store.TryLock(ctx, id, lockTTL)
		if err != nil {
			return nil, err
		}
		if acquired {
			defer unlock(ctx)
			return s.redeemRefreshToken(ctx, id)
		}
		s.opt.Metrics.TokenRefresh.WithLabelValues("waited").Inc()
		select {
		case <-ctx.Done():
			return nil, ErrIDPUnavailable
		case <-time.After(lockPoll):
		}
		sess, err := s.opt.Store.Get(ctx, id)
		if err != nil {
			return nil, err
		}
		if time.Until(sess.AccessExpiry) > refreshSkew {
			return sess, nil
		}
	}
}

// redeemRefreshToken runs under the lock.
func (s *Service) redeemRefreshToken(ctx context.Context, id string) (*session.Session, error) {
	// Another replica may have finished between this caller's check and taking the lock.
	sess, err := s.opt.Store.Get(ctx, id)
	if err != nil {
		return nil, err
	}
	if time.Until(sess.AccessExpiry) > refreshSkew {
		return sess, nil
	}
	client := s.client.Load()
	if client == nil {
		return nil, ErrIDPUnavailable
	}
	oauthCtx := s.oauthContext(ctx)
	token, err := client.oauth.TokenSource(oauthCtx, &oauth2.Token{RefreshToken: sess.RefreshToken}).Token()
	if err != nil {
		var re *oauth2.RetrieveError
		if errors.As(err, &re) && re.ErrorCode == "invalid_grant" {
			s.opt.Metrics.TokenRefresh.WithLabelValues("invalid_grant").Inc()
			if err := s.opt.Store.Delete(ctx, id); err != nil {
				s.opt.Logger.WarnContext(ctx, "deleting an ended session failed", "error", err.Error())
			}
			return nil, ErrSessionEnded
		}
		s.opt.Metrics.TokenRefresh.WithLabelValues("error").Inc()
		s.opt.Logger.WarnContext(ctx, "token refresh failed", "error", safeOAuthError(err))
		// The current token is still good for the rest of the skew window.
		if time.Now().Before(sess.AccessExpiry) {
			return sess, nil
		}
		return nil, ErrIDPUnavailable
	}
	if rawID, ok := token.Extra("id_token").(string); ok {
		idToken, err := client.verifier.Verify(oauthCtx, rawID)
		if err != nil || idToken.Subject != sess.Subject {
			s.opt.Metrics.TokenRefresh.WithLabelValues("invalid_id_token").Inc()
			if err := s.opt.Store.Delete(ctx, id); err != nil {
				s.opt.Logger.WarnContext(ctx, "deleting an ended session failed", "error", err.Error())
			}
			return nil, ErrSessionEnded
		}
	}
	sess.AccessToken = token.AccessToken
	sess.AccessExpiry = token.Expiry
	if token.RefreshToken != "" {
		sess.RefreshToken = token.RefreshToken
	}
	if err := s.opt.Store.Update(ctx, id, sess); err != nil {
		return nil, err
	}
	s.opt.Metrics.TokenRefresh.WithLabelValues("success").Inc()
	return sess, nil
}

// meResponse is everything the browser learns about the session. It has no token except the CSRF token.
type meResponse struct {
	UserID                 string   `json:"user_id"`
	Username               string   `json:"username"`
	Role                   string   `json:"role"`
	AllowedClassifications []string `json:"allowed_classifications"`
	CSRFToken              string   `json:"csrf_token"`
}

// Me reports the signed-in user. The role comes from the API, so its validation is the only role mapping there is.
func (s *Service) Me(w http.ResponseWriter, r *http.Request) {
	id := sessionID(r)
	if id == "" {
		writeError(w, http.StatusUnauthorized, "Not signed in")
		return
	}
	sess, err := s.freshSession(r.Context(), id)
	if err != nil {
		s.writeSessionError(w, r, err)
		return
	}
	req, err := http.NewRequestWithContext(r.Context(), http.MethodGet, s.opt.APIURL.JoinPath("v1", "me").String(), nil)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Cannot build the identity request")
		return
	}
	req.Header.Set("Authorization", "Bearer "+sess.AccessToken)
	res, err := s.opt.HTTPClient.Do(req)
	if err != nil {
		s.opt.Metrics.UpstreamError.Inc()
		writeError(w, http.StatusBadGateway, "The API is unavailable")
		return
	}
	defer func() { _ = res.Body.Close() }()
	switch res.StatusCode {
	case http.StatusOK:
	case http.StatusForbidden:
		writeError(w, http.StatusForbidden, "The account has no platform role")
		return
	case http.StatusUnauthorized:
		writeError(w, http.StatusUnauthorized, "The API rejected the session")
		return
	default:
		writeError(w, http.StatusBadGateway, "The API is unavailable")
		return
	}
	var identity struct {
		UserID                 string   `json:"user_id"`
		Role                   string   `json:"role"`
		AllowedClassifications []string `json:"allowed_classifications"`
	}
	if err := json.NewDecoder(res.Body).Decode(&identity); err != nil {
		writeError(w, http.StatusBadGateway, "The API sent an unreadable answer")
		return
	}
	writeJSON(w, http.StatusOK, meResponse{
		UserID:                 identity.UserID,
		Username:               sess.Username,
		Role:                   identity.Role,
		AllowedClassifications: identity.AllowedClassifications,
		CSRFToken:              sess.CSRFToken,
	})
}

// Logout ends the local session and the Keycloak session.
//
// It posts the refresh token from the server to the IdP's logout endpoint. RP-initiated logout through the browser
// would put the ID token in a URL, or show a confirmation page without it.
func (s *Service) Logout(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	id := sessionID(r)
	if id == "" {
		writeJSON(w, http.StatusOK, map[string]bool{"idp_session_ended": false})
		return
	}
	sess, err := s.opt.Store.Get(ctx, id)
	if errors.Is(err, session.ErrNotFound) {
		setCookie(w, SessionCookie, "", -1)
		writeJSON(w, http.StatusOK, map[string]bool{"idp_session_ended": false})
		return
	}
	if err != nil {
		s.writeSessionError(w, r, err)
		return
	}
	if !s.validCSRF(r, sess) {
		s.opt.Metrics.CSRFRejected.Inc()
		writeError(w, http.StatusForbidden, "CSRF check failed")
		return
	}
	if err := s.opt.Store.Delete(ctx, id); err != nil {
		s.writeSessionError(w, r, err)
		return
	}
	setCookie(w, SessionCookie, "", -1)
	ended := s.endIDPSession(ctx, sess.RefreshToken)
	label := "ended"
	if !ended {
		label = "failed"
	}
	s.opt.Metrics.Logouts.WithLabelValues(label).Inc()
	writeJSON(w, http.StatusOK, map[string]bool{"idp_session_ended": ended})
}

func (s *Service) endIDPSession(ctx context.Context, refreshToken string) bool {
	client := s.client.Load()
	if client == nil {
		return false
	}
	form := url.Values{
		"client_id":     {s.opt.ClientID},
		"client_secret": {s.opt.ClientSecret},
		"refresh_token": {refreshToken},
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, client.logoutURL, strings.NewReader(form.Encode()))
	if err != nil {
		return false
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	res, err := s.opt.HTTPClient.Do(req)
	if err != nil {
		s.opt.Logger.WarnContext(ctx, "ending the IdP session failed", "error", "logout endpoint unreachable")
		return false
	}
	defer func() { _ = res.Body.Close() }()
	if res.StatusCode >= http.StatusMultipleChoices {
		s.opt.Logger.WarnContext(ctx, "ending the IdP session failed", "status", res.StatusCode)
		return false
	}
	return true
}
