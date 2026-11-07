package session

import (
	"bytes"
	"context"
	"errors"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

func newTestStore(t *testing.T, key []byte) (*Store, *miniredis.Miniredis) {
	t.Helper()
	mr := miniredis.RunT(t)
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = rdb.Close() })
	store, err := NewStore(rdb, key, time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	return store, mr
}

func TestRoundTripAndEncryptionAtRest(t *testing.T) {
	store, mr := newTestStore(t, bytes.Repeat([]byte{1}, 32))
	ctx := context.Background()
	in := &Session{Subject: "sub", AccessToken: "plain-access", RefreshToken: "plain-refresh", CSRFToken: "c"}
	if err := store.Create(ctx, "id-1", in); err != nil {
		t.Fatal(err)
	}
	raw, err := mr.Get(sessionKey("id-1"))
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains([]byte(raw), []byte("plain-")) {
		t.Fatal("tokens are stored in clear")
	}
	out, err := store.Get(ctx, "id-1")
	if err != nil {
		t.Fatal(err)
	}
	if out.AccessToken != in.AccessToken || out.RefreshToken != in.RefreshToken || out.Subject != in.Subject {
		t.Fatalf("got %+v", out)
	}
}

func TestSameSessionEncryptsDifferentlyEachTime(t *testing.T) {
	store, _ := newTestStore(t, bytes.Repeat([]byte{1}, 32))
	a, err := store.seal("k", &Session{AccessToken: "x"})
	if err != nil {
		t.Fatal(err)
	}
	b, err := store.seal("k", &Session{AccessToken: "x"})
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Equal(a, b) {
		t.Fatal("the nonce repeated")
	}
}

func TestRecordCopiedToAnotherKeyDoesNotDecrypt(t *testing.T) {
	store, mr := newTestStore(t, bytes.Repeat([]byte{1}, 32))
	ctx := context.Background()
	if err := store.Create(ctx, "victim", &Session{AccessToken: "secret"}); err != nil {
		t.Fatal(err)
	}
	raw, err := mr.Get(sessionKey("victim"))
	if err != nil {
		t.Fatal(err)
	}
	if err := mr.Set(sessionKey("attacker"), raw); err != nil {
		t.Fatal(err)
	}
	if _, err := store.Get(ctx, "attacker"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v", err)
	}
}

func TestAnotherKeyCannotRead(t *testing.T) {
	store, mr := newTestStore(t, bytes.Repeat([]byte{1}, 32))
	ctx := context.Background()
	if err := store.Create(ctx, "id", &Session{AccessToken: "secret"}); err != nil {
		t.Fatal(err)
	}
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	t.Cleanup(func() { _ = rdb.Close() })
	other, err := NewStore(rdb, bytes.Repeat([]byte{2}, 32), time.Hour)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := other.Get(ctx, "id"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v", err)
	}
}

func TestRejectsShortKey(t *testing.T) {
	if _, err := NewStore(nil, []byte("short"), time.Hour); err == nil {
		t.Fatal("accepted a short key")
	}
}

func TestUpdateCannotResurrectAndKeepsTheAbsoluteLifetime(t *testing.T) {
	store, mr := newTestStore(t, bytes.Repeat([]byte{1}, 32))
	ctx := context.Background()
	if err := store.Update(ctx, "gone", &Session{}); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v", err)
	}
	if mr.Exists(sessionKey("gone")) {
		t.Fatal("update created a session")
	}
	if err := store.Create(ctx, "id", &Session{}); err != nil {
		t.Fatal(err)
	}
	mr.FastForward(30 * time.Minute)
	if err := store.Update(ctx, "id", &Session{AccessToken: "new"}); err != nil {
		t.Fatal(err)
	}
	if ttl := mr.TTL(sessionKey("id")); ttl > 31*time.Minute || ttl <= 0 {
		t.Fatalf("ttl = %v, want about 30m", ttl)
	}
	mr.FastForward(31 * time.Minute)
	if _, err := store.Get(ctx, "id"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v", err)
	}
}

func TestTakeLoginWorksOnce(t *testing.T) {
	store, mr := newTestStore(t, bytes.Repeat([]byte{1}, 32))
	ctx := context.Background()
	if err := store.SaveLogin(ctx, "state", &Login{Verifier: "v", Nonce: "n", ReturnTo: "/"}); err != nil {
		t.Fatal(err)
	}
	login, err := store.TakeLogin(ctx, "state")
	if err != nil || login.Verifier != "v" {
		t.Fatalf("login %+v, err %v", login, err)
	}
	if _, err := store.TakeLogin(ctx, "state"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("err = %v", err)
	}
	if err := store.SaveLogin(ctx, "state2", &Login{}); err != nil {
		t.Fatal(err)
	}
	mr.FastForward(loginTTL + time.Second)
	if _, err := store.TakeLogin(ctx, "state2"); !errors.Is(err, ErrNotFound) {
		t.Fatalf("expired login: err = %v", err)
	}
}

func TestLockExcludesAndOnlyTheOwnerReleases(t *testing.T) {
	store, mr := newTestStore(t, bytes.Repeat([]byte{1}, 32))
	ctx := context.Background()
	unlock, ok, err := store.TryLock(ctx, "id", time.Second)
	if err != nil || !ok {
		t.Fatalf("ok %v, err %v", ok, err)
	}
	if _, ok, _ := store.TryLock(ctx, "id", time.Second); ok {
		t.Fatal("second holder got the lock")
	}

	// The first holder's lock expires and a second holder takes over. A late unlock must not free the new lock.
	mr.FastForward(2 * time.Second)
	unlock2, ok, err := store.TryLock(ctx, "id", time.Minute)
	if err != nil || !ok {
		t.Fatalf("ok %v, err %v", ok, err)
	}
	unlock(ctx)
	if _, ok, _ := store.TryLock(ctx, "id", time.Second); ok {
		t.Fatal("a stale owner released the lock")
	}
	unlock2(ctx)
	if _, ok, _ := store.TryLock(ctx, "id", time.Second); !ok {
		t.Fatal("the owner could not release the lock")
	}
}
