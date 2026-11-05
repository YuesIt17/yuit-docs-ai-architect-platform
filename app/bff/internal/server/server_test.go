package server_test

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"io"
	"log/slog"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/redis/go-redis/v9"

	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/auth"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/obs"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/proxy"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/server"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/session"
	"github.com/YuesIt17/yuit-docs-ai-architect-platform/app/bff/internal/testidp"
)

var testKey = bytes.Repeat([]byte{7}, 32)

// syncBuffer collects logs from handler goroutines.
type syncBuffer struct {
	mu  sync.Mutex
	buf bytes.Buffer
}

func (b *syncBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.Write(p)
}

func (b *syncBuffer) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.buf.String()
}

// upstreamCall is what the API saw.
type upstreamCall struct {
	Path   string
	Query  string
	Header http.Header
}

type harness struct {
	t        *testing.T
	idp      *testidp.IDP
	redis    *miniredis.Miniredis
	api      *httptest.Server
	bff      *httptest.Server
	logs     *syncBuffer
	registry *prometheus.Registry

	mu    sync.Mutex
	calls []upstreamCall
}

func (h *harness) lastCall() upstreamCall {
	h.mu.Lock()
	defer h.mu.Unlock()
	if len(h.calls) == 0 {
		h.t.Fatal("the API received no request")
	}
	return h.calls[len(h.calls)-1]
}

func (h *harness) callCount() int {
	h.mu.Lock()
	defer h.mu.Unlock()
	return len(h.calls)
}

func (h *harness) apiHandler(w http.ResponseWriter, r *http.Request) {
	h.mu.Lock()
	h.calls = append(h.calls, upstreamCall{r.URL.Path, r.URL.RawQuery, r.Header.Clone()})
	h.mu.Unlock()
	switch r.URL.Path {
	case "/v1/me":
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"user_id":"user-sub-1","role":"category_manager","name":"manager","allowed_classifications":["internal","public"]}`)
	case "/v1/set-cookie":
		w.Header().Set("Set-Cookie", "tracking=1")
		w.WriteHeader(http.StatusOK)
	default:
		w.WriteHeader(http.StatusOK)
	}
}

func newService(t *testing.T, idp *testidp.IDP, redisAddr, publicURL string, api *url.URL, m *obs.Metrics, log *slog.Logger) *auth.Service {
	t.Helper()
	rdb := redis.NewClient(&redis.Options{Addr: redisAddr})
	t.Cleanup(func() { _ = rdb.Close() })
	store, err := session.NewStore(rdb, testKey, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	svc, err := auth.New(auth.Options{
		PublicURL:    publicURL,
		Issuer:       idp.Issuer(),
		DiscoveryURL: idp.Issuer(),
		ClientID:     testidp.ClientID,
		ClientSecret: testidp.ClientSecret,
		Scopes:       []string{"openid", "profile"},
		APIURL:       api,
		HTTPClient:   &http.Client{Timeout: 5 * time.Second},
		Store:        store,
		Metrics:      m,
		Logger:       log,
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := svc.Connect(context.Background()); err != nil {
		t.Fatal(err)
	}
	return svc
}

func newHarness(t *testing.T) *harness {
	t.Helper()
	h := &harness{t: t, idp: testidp.New(t), logs: &syncBuffer{}, registry: prometheus.NewRegistry()}
	h.redis = miniredis.RunT(t)
	h.api = httptest.NewServer(http.HandlerFunc(h.apiHandler))
	t.Cleanup(h.api.Close)
	h.bff = h.startBFF()
	t.Cleanup(h.bff.Close)
	return h
}

func (h *harness) startBFF() *httptest.Server {
	h.t.Helper()
	log := obs.NewLogger(h.logs, "DEBUG")
	metrics := obs.NewMetrics(h.registry)
	apiURL, err := url.Parse(h.api.URL)
	if err != nil {
		h.t.Fatal(err)
	}
	var handler atomic.Value
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		handler.Load().(http.Handler).ServeHTTP(w, r) //nolint:forcetypeassert // set just below
	}))
	svc := newService(h.t, h.idp, h.redis.Addr(), srv.URL, apiURL, metrics, log)
	handler.Store(server.PublicHandler(svc, proxy.New(apiURL, proxy.NewTransport(), metrics, log), metrics, log))
	return srv
}

// browser keeps cookies by name and sends them all. net/http/cookiejar would withhold Secure cookies over HTTP,
// and these tests run on plain HTTP against httptest.
type browser struct {
	t       *testing.T
	client  *http.Client
	cookies map[string]string
	set     map[string]*http.Cookie
}

func newBrowser(t *testing.T) *browser {
	t.Helper()
	return &browser{
		t: t,
		client: &http.Client{
			Timeout:       10 * time.Second,
			CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
		},
		cookies: map[string]string{},
		set:     map[string]*http.Cookie{},
	}
}

func (b *browser) do(method, target string, body io.Reader, header map[string]string) *http.Response {
	b.t.Helper()
	req, err := http.NewRequestWithContext(context.Background(), method, target, body)
	if err != nil {
		b.t.Fatal(err)
	}
	for name, value := range b.cookies {
		req.AddCookie(&http.Cookie{Name: name, Value: value})
	}
	for k, v := range header {
		req.Header.Set(k, v)
	}
	res, err := b.client.Do(req)
	if err != nil {
		b.t.Fatal(err)
	}
	for _, c := range res.Cookies() {
		b.set[c.Name] = c
		if c.MaxAge < 0 {
			delete(b.cookies, c.Name)
		} else {
			b.cookies[c.Name] = c.Value
		}
	}
	return res
}

func (b *browser) status(method, target string, header map[string]string) int {
	b.t.Helper()
	res := b.do(method, target, nil, header)
	defer res.Body.Close()
	_, _ = io.Copy(io.Discard, res.Body)
	return res.StatusCode
}

func location(t *testing.T, res *http.Response) string {
	t.Helper()
	defer res.Body.Close()
	if res.StatusCode != http.StatusFound {
		t.Fatalf("status = %d, want 302", res.StatusCode)
	}
	return res.Header.Get("Location")
}

// startLogin returns the callback URL the IdP redirected to.
func (h *harness) startLogin(b *browser) string {
	h.t.Helper()
	authorize := location(h.t, b.do(http.MethodGet, h.bff.URL+"/auth/login", nil, nil))
	return location(h.t, b.do(http.MethodGet, authorize, nil, nil))
}

func (h *harness) login(b *browser) {
	h.t.Helper()
	if got := location(h.t, b.do(http.MethodGet, h.startLogin(b), nil, nil)); got != "/" {
		h.t.Fatalf("after login redirected to %q", got)
	}
	if b.cookies[auth.SessionCookie] == "" {
		h.t.Fatal("no session cookie after login")
	}
}

func (h *harness) csrf(b *browser) string {
	h.t.Helper()
	res := b.do(http.MethodGet, h.bff.URL+"/auth/me", nil, nil)
	defer res.Body.Close()
	var me struct {
		CSRFToken string `json:"csrf_token"`
	}
	if err := json.NewDecoder(res.Body).Decode(&me); err != nil {
		h.t.Fatal(err)
	}
	if me.CSRFToken == "" {
		h.t.Fatal("no CSRF token")
	}
	return me.CSRFToken
}

func TestLoginSetsStrictCookieAndExposesNoToken(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)

	cookie := b.set[auth.SessionCookie]
	if !cookie.HttpOnly || !cookie.Secure || cookie.SameSite != http.SameSiteLaxMode || cookie.Path != "/" || cookie.Domain != "" {
		t.Fatalf("weak cookie: %+v", cookie)
	}
	if strings.Contains(cookie.Value, "access-") || strings.Contains(cookie.Value, "refresh-") {
		t.Fatal("the cookie carries a token")
	}

	res := b.do(http.MethodGet, h.bff.URL+"/auth/me", nil, nil)
	defer res.Body.Close()
	body, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatal(err)
	}
	if res.StatusCode != http.StatusOK {
		t.Fatalf("/auth/me = %d", res.StatusCode)
	}
	var me map[string]any
	if err := json.Unmarshal(body, &me); err != nil {
		t.Fatal(err)
	}
	if me["role"] != "category_manager" || me["username"] != "manager" || me["user_id"] != testidp.Subject {
		t.Fatalf("/auth/me = %s", body)
	}
	for _, leaked := range []string{"access-", "refresh-", "eyJ"} {
		if strings.Contains(string(body), leaked) {
			t.Fatalf("/auth/me leaks %q: %s", leaked, body)
		}
	}
}

func TestLoginRedirectCarriesPKCEStateAndNonce(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	target, err := url.Parse(location(t, b.do(http.MethodGet, h.bff.URL+"/auth/login", nil, nil)))
	if err != nil {
		t.Fatal(err)
	}
	q := target.Query()
	if q.Get("code_challenge_method") != "S256" || q.Get("code_challenge") == "" || q.Get("state") == "" || q.Get("nonce") == "" {
		t.Fatalf("authorization request: %v", q)
	}
	if strings.Contains(target.String(), "code_verifier") {
		t.Fatal("the verifier reached the browser")
	}
}

func TestTokensAreEncryptedInRedisAndKeysHideTheSessionID(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)
	id := b.cookies[auth.SessionCookie]
	keys := h.redis.Keys()
	if len(keys) == 0 {
		t.Fatal("nothing stored")
	}
	for _, key := range keys {
		if strings.Contains(key, id) {
			t.Fatalf("key %q contains the session id", key)
		}
		value, err := h.redis.Get(key)
		if err != nil {
			t.Fatal(err)
		}
		for _, secret := range []string{"access-", "refresh-", testidp.Subject} {
			if strings.Contains(value, secret) {
				t.Fatalf("redis value holds %q in clear", secret)
			}
		}
	}
}

func TestCallbackRejectsForgedOrReplayedRequests(t *testing.T) {
	h := newHarness(t)

	t.Run("state differs from the cookie", func(t *testing.T) {
		b := newBrowser(t)
		callback := h.startLogin(b)
		u, err := url.Parse(callback)
		if err != nil {
			t.Fatal(err)
		}
		q := u.Query()
		q.Set("state", "forged")
		u.RawQuery = q.Encode()
		got := location(t, b.do(http.MethodGet, u.String(), nil, nil))
		if got != "/?login_error=invalid_state" || b.cookies[auth.SessionCookie] != "" {
			t.Fatalf("redirect %q, cookies %v", got, b.cookies)
		}
	})

	t.Run("login started in another browser", func(t *testing.T) {
		callback := h.startLogin(newBrowser(t))
		victim := newBrowser(t)
		got := location(t, victim.do(http.MethodGet, callback, nil, nil))
		if got != "/?login_error=invalid_state" || victim.cookies[auth.SessionCookie] != "" {
			t.Fatalf("redirect %q, cookies %v", got, victim.cookies)
		}
	})

	t.Run("attacker's callback in a victim's own login", func(t *testing.T) {
		attackerCallback := h.startLogin(newBrowser(t))
		victim := newBrowser(t)
		h.startLogin(victim)
		got := location(t, victim.do(http.MethodGet, attackerCallback, nil, nil))
		if got != "/?login_error=invalid_state" || victim.cookies[auth.SessionCookie] != "" {
			t.Fatalf("redirect %q, cookies %v", got, victim.cookies)
		}
	})

	t.Run("replayed callback", func(t *testing.T) {
		b := newBrowser(t)
		callback := h.startLogin(b)
		state := b.cookies["__Host-kp_login"]
		location(t, b.do(http.MethodGet, callback, nil, nil))
		b.cookies["__Host-kp_login"] = state
		delete(b.cookies, auth.SessionCookie)
		got := location(t, b.do(http.MethodGet, callback, nil, nil))
		if got != "/?login_error=invalid_state" || b.cookies[auth.SessionCookie] != "" {
			t.Fatalf("redirect %q, cookies %v", got, b.cookies)
		}
	})

	t.Run("error from the IdP", func(t *testing.T) {
		b := newBrowser(t)
		h.startLogin(b)
		got := location(t, b.do(http.MethodGet,
			h.bff.URL+"/auth/callback?error=access_denied&state="+b.cookies["__Host-kp_login"], nil, nil))
		if got != "/?login_error=idp_denied" {
			t.Fatalf("redirect %q", got)
		}
	})
}

func TestCallbackRejectsWrongNonce(t *testing.T) {
	h := newHarness(t)
	h.idp.NonceOverride = "attacker-nonce"
	b := newBrowser(t)
	got := location(t, b.do(http.MethodGet, h.startLogin(b), nil, nil))
	if got != "/?login_error=invalid_nonce" || b.cookies[auth.SessionCookie] != "" {
		t.Fatalf("redirect %q, cookies %v", got, b.cookies)
	}
}

func TestReturnToCannotLeaveTheOrigin(t *testing.T) {
	h := newHarness(t)
	for input, want := range map[string]string{
		"/labels":           "/labels",
		"//evil.example":    "/",
		"https://evil.test": "/",
		"/\\evil.example":   "/",
		"":                  "/",
	} {
		b := newBrowser(t)
		authorize := location(t, b.do(http.MethodGet, h.bff.URL+"/auth/login?return_to="+url.QueryEscape(input), nil, nil))
		callback := location(t, b.do(http.MethodGet, authorize, nil, nil))
		if got := location(t, b.do(http.MethodGet, callback, nil, nil)); got != want {
			t.Errorf("return_to %q redirected to %q, want %q", input, got, want)
		}
	}
}

func TestNewLoginReplacesTheOldSession(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)
	first := b.cookies[auth.SessionCookie]
	h.login(b)
	if b.cookies[auth.SessionCookie] == first {
		t.Fatal("session id was reused across logins")
	}
	stale := newBrowser(t)
	stale.cookies[auth.SessionCookie] = first
	if code := stale.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil); code != http.StatusUnauthorized {
		t.Fatalf("old session answered %d", code)
	}
}

func TestProxyRequiresASession(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	for _, target := range []string{"/api/v1/x", "/api/health", "/auth/me"} {
		if code := b.status(http.MethodGet, h.bff.URL+target, nil); code != http.StatusUnauthorized {
			t.Errorf("%s = %d, want 401", target, code)
		}
	}
	if n := h.callCount(); n != 0 {
		t.Fatalf("the API got %d unauthenticated requests", n)
	}
	b.cookies[auth.SessionCookie] = "made-up"
	if code := b.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil); code != http.StatusUnauthorized {
		t.Fatalf("made-up session = %d", code)
	}
}

func TestProxyReplacesCredentialsAndStripsTheAPIPrefix(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)
	code := b.status(http.MethodGet, h.bff.URL+"/api/v1/graph/subgraph?seed=gluten", map[string]string{
		"Authorization":       "Bearer forged-by-the-browser",
		"Proxy-Authorization": "Basic Zm9v",
	})
	if code != http.StatusOK {
		t.Fatalf("status %d", code)
	}
	call := h.lastCall()
	if call.Path != "/v1/graph/subgraph" || call.Query != "seed=gluten" {
		t.Fatalf("upstream saw %s?%s", call.Path, call.Query)
	}
	if got := call.Header.Values("Authorization"); len(got) != 1 || !strings.HasPrefix(got[0], "Bearer access-") {
		t.Fatalf("Authorization = %v", got)
	}
	for _, header := range []string{"Cookie", "Proxy-Authorization", "X-Csrf-Token"} {
		if call.Header.Get(header) != "" {
			t.Fatalf("%s reached the API", header)
		}
	}
}

func TestPublicModeRouteHasNoCredentials(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	code := b.status(http.MethodGet, h.bff.URL+"/api/v1/auth/mode", map[string]string{"Authorization": "Bearer forged"})
	if code != http.StatusOK {
		t.Fatalf("status %d", code)
	}
	if got := h.lastCall().Header.Get("Authorization"); got != "" {
		t.Fatalf("Authorization = %q", got)
	}
}

func TestProxyOnlyReachesAllowedPaths(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)
	before := h.callCount()
	for _, target := range []string{"/api/metrics", "/api/docs", "/api/openapi.json", "/api/v1/../metrics", "/api/%2e%2e/metrics", "/api/v1/%2e%2e/metrics"} {
		code := b.status(http.MethodGet, h.bff.URL+target, nil)
		if code == http.StatusOK {
			t.Errorf("%s reached the API", target)
		}
	}
	for i := before; i < h.callCount(); i++ {
		h.mu.Lock()
		p := h.calls[i].Path
		h.mu.Unlock()
		if p == "/metrics" || p == "/docs" {
			t.Errorf("the API served %s", p)
		}
	}
}

func TestProxyDropsSetCookieFromTheAPI(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)
	res := b.do(http.MethodGet, h.bff.URL+"/api/v1/set-cookie", nil, nil)
	defer res.Body.Close()
	if res.Header.Get("Set-Cookie") != "" {
		t.Fatal("Set-Cookie from the API reached the browser")
	}
}

func TestCSRFProtectsStateChangingRequests(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)
	token := h.csrf(b)
	target := h.bff.URL + "/api/v1/chat"

	cases := []struct {
		name   string
		header map[string]string
		want   int
	}{
		{"no token", nil, http.StatusForbidden},
		{"wrong token", map[string]string{auth.CSRFHeader: "wrong"}, http.StatusForbidden},
		{"cross-site fetch", map[string]string{auth.CSRFHeader: token, "Sec-Fetch-Site": "cross-site"}, http.StatusForbidden},
		{"foreign origin", map[string]string{auth.CSRFHeader: token, "Origin": "https://evil.example"}, http.StatusForbidden},
		{"valid", map[string]string{auth.CSRFHeader: token, "Sec-Fetch-Site": "same-origin"}, http.StatusOK},
		{"valid from public origin", map[string]string{auth.CSRFHeader: token, "Origin": h.bff.URL}, http.StatusOK},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if code := b.status(http.MethodPost, target, tc.header); code != tc.want {
				t.Fatalf("status %d, want %d", code, tc.want)
			}
		})
	}
	if got := h.lastCall().Header.Get(auth.CSRFHeader); got != "" {
		t.Fatal("the CSRF token reached the API")
	}
}

func TestConcurrentRequestsRefreshOnce(t *testing.T) {
	h := newHarness(t)
	h.idp.AccessTTL = time.Second // Within the refresh skew, so the first token already needs renewing.
	b := newBrowser(t)
	h.login(b)
	h.idp.AccessTTL = 5 * time.Minute
	h.idp.RefreshDelay = 150 * time.Millisecond

	const requests = 40
	var wg sync.WaitGroup
	codes := make([]int, requests)
	cookie := b.cookies[auth.SessionCookie]
	for i := range requests {
		wg.Add(1)
		go func() {
			defer wg.Done()
			one := newBrowser(t)
			one.cookies[auth.SessionCookie] = cookie
			codes[i] = one.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil)
		}()
	}
	wg.Wait()
	for i, code := range codes {
		if code != http.StatusOK {
			t.Fatalf("request %d = %d", i, code)
		}
	}
	if calls := h.idp.RefreshCalls.Load(); calls != 1 {
		t.Fatalf("%d refreshes, want 1", calls)
	}
	if h.idp.ReuseDetected.Load() != 0 {
		t.Fatal("a rotated refresh token was reused")
	}
}

func TestTwoReplicasRefreshOnce(t *testing.T) {
	h := newHarness(t)
	second := h.startBFF2()
	h.idp.AccessTTL = time.Second
	b := newBrowser(t)
	h.login(b)
	h.idp.AccessTTL = 5 * time.Minute
	h.idp.RefreshDelay = 200 * time.Millisecond

	var wg sync.WaitGroup
	cookie := b.cookies[auth.SessionCookie]
	codes := make([]int, 20)
	for i := range codes {
		base := h.bff.URL
		if i%2 == 1 {
			base = second.URL
		}
		wg.Add(1)
		go func() {
			defer wg.Done()
			one := newBrowser(t)
			one.cookies[auth.SessionCookie] = cookie
			codes[i] = one.status(http.MethodGet, base+"/api/v1/x", nil)
		}()
	}
	wg.Wait()
	for i, code := range codes {
		if code != http.StatusOK {
			t.Fatalf("request %d = %d", i, code)
		}
	}
	if calls := h.idp.RefreshCalls.Load(); calls != 1 {
		t.Fatalf("%d refreshes across replicas, want 1", calls)
	}
	if h.idp.ReuseDetected.Load() != 0 {
		t.Fatal("a rotated refresh token was reused")
	}
}

// startBFF2 runs a second replica with its own process state and the same Redis.
func (h *harness) startBFF2() *httptest.Server {
	h.t.Helper()
	log := obs.NewLogger(h.logs, "DEBUG")
	metrics := obs.NewMetrics(prometheus.NewRegistry())
	apiURL, err := url.Parse(h.api.URL)
	if err != nil {
		h.t.Fatal(err)
	}
	svc := newService(h.t, h.idp, h.redis.Addr(), h.bff.URL, apiURL, metrics, log)
	srv := httptest.NewServer(server.PublicHandler(svc, proxy.New(apiURL, proxy.NewTransport(), metrics, log), metrics, log))
	h.t.Cleanup(srv.Close)
	return srv
}

func TestRefreshRotatesTokens(t *testing.T) {
	h := newHarness(t)
	h.idp.AccessTTL = time.Second
	b := newBrowser(t)
	h.login(b)
	if code := b.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil); code != http.StatusOK {
		t.Fatalf("status %d", code)
	}
	first := h.lastCall().Header.Get("Authorization")
	if code := b.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil); code != http.StatusOK {
		t.Fatalf("status %d", code)
	}
	if second := h.lastCall().Header.Get("Authorization"); first == second {
		t.Fatal("the access token did not change")
	}
	if calls := h.idp.RefreshCalls.Load(); calls < 2 {
		t.Fatalf("%d refreshes", calls)
	}
	if h.idp.ReuseDetected.Load() != 0 {
		t.Fatal("the BFF redeemed an old refresh token")
	}
}

func TestRevokedRefreshTokenEndsTheSession(t *testing.T) {
	h := newHarness(t)
	h.idp.AccessTTL = time.Second
	b := newBrowser(t)
	h.login(b)
	h.idp.Revoke()
	if code := b.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil); code != http.StatusUnauthorized {
		t.Fatalf("status %d", code)
	}
	if b.cookies[auth.SessionCookie] != "" {
		t.Fatal("the cookie of a dead session was kept")
	}
}

func TestIdPOutageDoesNotEndTheSession(t *testing.T) {
	h := newHarness(t)
	h.idp.AccessTTL = 2 * time.Second
	b := newBrowser(t)
	h.login(b)
	h.idp.RefreshDown.Store(true)

	// The token is inside the refresh skew but not yet expired, so it is still served.
	if code := b.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil); code != http.StatusOK {
		t.Fatalf("still-valid token: status %d", code)
	}
	time.Sleep(2100 * time.Millisecond)
	if code := b.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil); code != http.StatusServiceUnavailable {
		t.Fatalf("expired token during an outage: status %d", code)
	}
	h.idp.RefreshDown.Store(false)
	if code := b.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil); code != http.StatusOK {
		t.Fatalf("after the outage: status %d", code)
	}
}

func TestLogoutEndsBothSessions(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)
	token := h.csrf(b)
	cookie := b.cookies[auth.SessionCookie]

	if code := b.status(http.MethodPost, h.bff.URL+"/auth/logout", nil); code != http.StatusForbidden {
		t.Fatalf("logout without CSRF token = %d", code)
	}
	if h.idp.LoggedOut.Load() != 0 {
		t.Fatal("the IdP session ended without a CSRF token")
	}

	res := b.do(http.MethodPost, h.bff.URL+"/auth/logout", nil, map[string]string{auth.CSRFHeader: token})
	defer res.Body.Close()
	var body struct {
		Ended bool `json:"idp_session_ended"`
	}
	if err := json.NewDecoder(res.Body).Decode(&body); err != nil {
		t.Fatal(err)
	}
	if res.StatusCode != http.StatusOK || !body.Ended || h.idp.LoggedOut.Load() != 1 {
		t.Fatalf("status %d, body %+v, idp logouts %d", res.StatusCode, body, h.idp.LoggedOut.Load())
	}
	if b.cookies[auth.SessionCookie] != "" {
		t.Fatal("the cookie was not cleared")
	}
	replayed := newBrowser(t)
	replayed.cookies[auth.SessionCookie] = cookie
	if code := replayed.status(http.MethodGet, h.bff.URL+"/api/v1/x", nil); code != http.StatusUnauthorized {
		t.Fatalf("session after logout = %d", code)
	}
}

func TestLogsNeverContainTokensOrCodes(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)
	h.csrf(b)
	callbackLogged := strings.Contains(h.logs.String(), "/auth/callback")
	if !callbackLogged {
		t.Fatal("the test did not exercise the callback log line")
	}
	logs := h.logs.String()
	for _, secret := range []string{"access-", "refresh-", "code=", "state=", "eyJ", testidp.ClientSecret, b.cookies[auth.SessionCookie]} {
		if strings.Contains(logs, secret) {
			t.Fatalf("logs contain %q:\n%s", secret, logs)
		}
	}
}

func TestLogLinesUseTheAPIFieldNames(t *testing.T) {
	var buf bytes.Buffer
	obs.NewLogger(&buf, "INFO").Info("hello")
	var line map[string]any
	if err := json.Unmarshal(buf.Bytes(), &line); err != nil {
		t.Fatal(err)
	}
	for field, want := range map[string]string{"service": "kp-bff", "level": "info", "logger": "bff", "msg": "hello"} {
		if line[field] != want {
			t.Errorf("%s = %v, want %s", field, line[field], want)
		}
	}
	if _, ok := line["ts"]; !ok {
		t.Error("no ts field")
	}
}

// streamingUpstream sends one SSE event, then waits until released before the next.
func streamingUpstream(t *testing.T, release <-chan struct{}) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v1/me" {
			return
		}
		w.Header().Set("Content-Type", "text/event-stream")
		flusher, ok := w.(http.Flusher)
		if !ok {
			t.Error("no flusher")
			return
		}
		_, _ = io.WriteString(w, "event: meta\ndata: {}\n\n")
		flusher.Flush()
		select {
		case <-release:
		case <-r.Context().Done():
			return
		}
		_, _ = io.WriteString(w, "event: final\ndata: {}\n\n")
		flusher.Flush()
	}))
	t.Cleanup(srv.Close)
	return srv
}

// TestStreamFlushesAtOnceAndOutlivesWriteTimeout runs the real http.Server with a short WriteTimeout through the whole
// middleware chain. The first event must arrive while the upstream is still open, and the second after the timeout.
func TestStreamFlushesAtOnceAndOutlivesWriteTimeout(t *testing.T) {
	idp := testidp.New(t)
	mr := miniredis.RunT(t)
	logs := &syncBuffer{}
	log := obs.NewLogger(logs, "INFO")
	metrics := obs.NewMetrics(prometheus.NewRegistry())
	release := make(chan struct{})
	upstream := streamingUpstream(t, release)
	apiURL, err := url.Parse(upstream.URL)
	if err != nil {
		t.Fatal(err)
	}

	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	public := "http://" + listener.Addr().String()
	svc := newService(t, idp, mr.Addr(), public, apiURL, metrics, log)
	const writeTimeout = 300 * time.Millisecond
	srv := &http.Server{
		Handler:           server.PublicHandler(svc, proxy.New(apiURL, proxy.NewTransport(), metrics, log), metrics, log),
		ReadHeaderTimeout: time.Second,
		WriteTimeout:      writeTimeout,
	}
	go func() { _ = srv.Serve(listener) }()
	t.Cleanup(func() { _ = srv.Close() })

	h := &harness{t: t, bff: &httptest.Server{URL: public}}
	b := newBrowser(t)
	b.client.Timeout = 0
	h.login(b)

	res := b.do(http.MethodGet, public+"/api/v1/stream", nil, nil)
	defer res.Body.Close()
	if res.StatusCode != http.StatusOK || !strings.HasPrefix(res.Header.Get("Content-Type"), "text/event-stream") {
		t.Fatalf("status %d, type %q", res.StatusCode, res.Header.Get("Content-Type"))
	}
	reader := bufio.NewReader(res.Body)

	readLine := func() (string, error) {
		type result struct {
			line string
			err  error
		}
		ch := make(chan result, 1)
		go func() {
			line, err := reader.ReadString('\n')
			ch <- result{line, err}
		}()
		select {
		case r := <-ch:
			return r.line, r.err
		case <-time.After(5 * time.Second):
			return "", context.DeadlineExceeded
		}
	}

	first, err := readLine()
	if err != nil || first != "event: meta\n" {
		t.Fatalf("first event not flushed while the upstream stayed open: %q, %v", first, err)
	}
	for range 2 { // data line and blank line
		if _, err := readLine(); err != nil {
			t.Fatal(err)
		}
	}

	time.Sleep(3 * writeTimeout)
	close(release)

	second, err := readLine()
	if err != nil || second != "event: final\n" {
		t.Fatalf("stream cut after the write timeout: %q, %v", second, err)
	}
}

func TestShortResponsesKeepTheWriteTimeoutConfigured(t *testing.T) {
	srv := server.NewPublicServer(":0", http.NewServeMux())
	if srv.WriteTimeout != server.WriteTimeout || srv.WriteTimeout == 0 {
		t.Fatalf("WriteTimeout = %v", srv.WriteTimeout)
	}
	if srv.ReadHeaderTimeout == 0 || srv.IdleTimeout == 0 {
		t.Fatal("missing timeouts")
	}
}

func TestAdminEndpoints(t *testing.T) {
	h := newHarness(t)
	b := newBrowser(t)
	h.login(b)
	metrics := obs.NewMetrics(prometheus.NewRegistry())
	idp := testidp.New(t)
	apiURL, err := url.Parse(h.api.URL)
	if err != nil {
		t.Fatal(err)
	}
	ready := newService(t, idp, h.redis.Addr(), h.bff.URL, apiURL, metrics, obs.NewLogger(io.Discard, "INFO"))

	var pingErr error
	admin := httptest.NewServer(server.AdminHandler(ready, func(context.Context) error { return pingErr }, h.registry))
	t.Cleanup(admin.Close)

	if code := b.status(http.MethodGet, admin.URL+"/healthz", nil); code != http.StatusOK {
		t.Fatalf("/healthz = %d", code)
	}
	if code := b.status(http.MethodGet, admin.URL+"/readyz", nil); code != http.StatusOK {
		t.Fatalf("/readyz = %d", code)
	}
	pingErr = context.DeadlineExceeded
	if code := b.status(http.MethodGet, admin.URL+"/readyz", nil); code != http.StatusServiceUnavailable {
		t.Fatalf("/readyz without redis = %d", code)
	}

	res := b.do(http.MethodGet, admin.URL+"/metrics", nil, nil)
	defer res.Body.Close()
	body, err := io.ReadAll(res.Body)
	if err != nil {
		t.Fatal(err)
	}
	for _, series := range []string{"bff_http_requests_total", "bff_logins_total", "bff_http_request_duration_seconds"} {
		if !strings.Contains(string(body), series) {
			t.Errorf("metrics lack %s", series)
		}
	}
}

func TestNotReadyBeforeDiscovery(t *testing.T) {
	mr := miniredis.RunT(t)
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = rdb.Close() })
	store, err := session.NewStore(rdb, testKey, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	svc, err := auth.New(auth.Options{
		PublicURL: "https://kp.example", Store: store,
		Metrics: obs.NewMetrics(prometheus.NewRegistry()), Logger: obs.NewLogger(io.Discard, "INFO"),
	})
	if err != nil {
		t.Fatal(err)
	}
	if svc.Ready() {
		t.Fatal("ready without metadata")
	}
	rec := httptest.NewRecorder()
	svc.Login(rec, httptest.NewRequest(http.MethodGet, "/auth/login", nil))
	if rec.Code != http.StatusServiceUnavailable {
		t.Fatalf("login before discovery = %d", rec.Code)
	}
}

func TestDiscoveryRejectsMetadataForAnotherIssuer(t *testing.T) {
	idp := testidp.New(t)
	mr := miniredis.RunT(t)
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = rdb.Close() })
	store, err := session.NewStore(rdb, testKey, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	svc, err := auth.New(auth.Options{
		PublicURL:    "https://kp.example",
		Issuer:       "https://kp.example/idp/realms/kp",
		DiscoveryURL: idp.Issuer(),
		ClientID:     testidp.ClientID,
		HTTPClient:   http.DefaultClient,
		Store:        store,
		Metrics:      obs.NewMetrics(prometheus.NewRegistry()),
		Logger:       obs.NewLogger(io.Discard, "INFO"),
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := svc.Connect(context.Background()); err == nil {
		t.Fatal("metadata for another issuer was accepted")
	}
}
