// Package session keeps login state and tokens in Redis, encrypted at rest and keyed by a hash of an opaque id.
package session

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

// ErrNotFound means the session or login state is absent, expired or unreadable.
var ErrNotFound = errors.New("session: not found")

// loginTTL bounds how long a login can stay in progress at the IdP.
const loginTTL = 10 * time.Minute

// Session is what the BFF holds for a signed-in browser. No part of it is sent to the browser except CSRFToken.
type Session struct {
	Subject      string    `json:"sub"`
	Username     string    `json:"username"`
	AccessToken  string    `json:"access_token"`
	RefreshToken string    `json:"refresh_token"`
	AccessExpiry time.Time `json:"access_expiry"`
	CSRFToken    string    `json:"csrf_token"`
}

// Login is the state of an authorization request between /auth/login and /auth/callback.
type Login struct {
	Verifier string `json:"verifier"`
	Nonce    string `json:"nonce"`
	ReturnTo string `json:"return_to"`
}

// Store reads and writes sessions. A dump of Redis yields neither tokens nor usable session ids.
type Store struct {
	rdb  redis.UniversalClient
	aead cipher.AEAD
	ttl  time.Duration
}

// NewStore needs a 32-byte key for AES-256-GCM.
func NewStore(rdb redis.UniversalClient, key []byte, ttl time.Duration) (*Store, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("session: cipher: %w", err)
	}
	// The stdlib generates and prepends the nonce, so this package has no nonce handling to get wrong.
	aead, err := cipher.NewGCMWithRandomNonce(block)
	if err != nil {
		return nil, fmt.Errorf("session: gcm: %w", err)
	}
	return &Store{rdb: rdb, aead: aead, ttl: ttl}, nil
}

// NewID returns an unguessable opaque id.
func NewID() string { return rand.Text() }

func hashed(prefix, id string) string {
	sum := sha256.Sum256([]byte(id))
	return prefix + hex.EncodeToString(sum[:])
}

func sessionKey(id string) string  { return hashed("bff:session:", id) }
func loginKey(state string) string { return hashed("bff:login:", state) }
func lockKey(id string) string     { return hashed("bff:lock:", id) }

// seal binds the ciphertext to its Redis key, so a record copied under another key does not decrypt.
func (s *Store) seal(key string, v any) ([]byte, error) {
	plain, err := json.Marshal(v)
	if err != nil {
		return nil, fmt.Errorf("session: encode: %w", err)
	}
	return s.aead.Seal(nil, nil, plain, []byte(key)), nil //nolint:gosec // NewGCMWithRandomNonce generates the nonce.
}

func (s *Store) open(key string, sealed []byte, v any) error {
	plain, err := s.aead.Open(nil, nil, sealed, []byte(key))
	if err != nil {
		return ErrNotFound
	}
	if err := json.Unmarshal(plain, v); err != nil {
		return ErrNotFound
	}
	return nil
}

// Create stores a new session. The TTL is an absolute lifetime, and refreshes do not extend it.
func (s *Store) Create(ctx context.Context, id string, sess *Session) error {
	key := sessionKey(id)
	sealed, err := s.seal(key, sess)
	if err != nil {
		return err
	}
	return s.rdb.Set(ctx, key, sealed, s.ttl).Err()
}

// Update replaces a session that still exists, so a refresh racing a logout cannot bring it back.
func (s *Store) Update(ctx context.Context, id string, sess *Session) error {
	key := sessionKey(id)
	sealed, err := s.seal(key, sess)
	if err != nil {
		return err
	}
	err = s.rdb.SetArgs(ctx, key, sealed, redis.SetArgs{Mode: "XX", KeepTTL: true}).Err()
	if errors.Is(err, redis.Nil) {
		return ErrNotFound
	}
	return err
}

// Get returns the session, or ErrNotFound.
func (s *Store) Get(ctx context.Context, id string) (*Session, error) {
	key := sessionKey(id)
	sealed, err := s.rdb.Get(ctx, key).Bytes()
	if errors.Is(err, redis.Nil) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("session: get: %w", err)
	}
	var sess Session
	if err := s.open(key, sealed, &sess); err != nil {
		return nil, err
	}
	return &sess, nil
}

// Delete removes the session.
func (s *Store) Delete(ctx context.Context, id string) error {
	return s.rdb.Del(ctx, sessionKey(id)).Err()
}

// SaveLogin stores an authorization request under its state value.
func (s *Store) SaveLogin(ctx context.Context, state string, login *Login) error {
	key := loginKey(state)
	sealed, err := s.seal(key, login)
	if err != nil {
		return err
	}
	return s.rdb.Set(ctx, key, sealed, loginTTL).Err()
}

// TakeLogin returns and removes the authorization request, so a callback cannot be replayed.
func (s *Store) TakeLogin(ctx context.Context, state string) (*Login, error) {
	key := loginKey(state)
	sealed, err := s.rdb.GetDel(ctx, key).Bytes()
	if errors.Is(err, redis.Nil) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("session: take login: %w", err)
	}
	var login Login
	if err := s.open(key, sealed, &login); err != nil {
		return nil, err
	}
	return &login, nil
}

var unlockScript = redis.NewScript(`
if redis.call("GET", KEYS[1]) == ARGV[1] then
  return redis.call("DEL", KEYS[1])
end
return 0`)

// TryLock takes the per-session refresh lock shared by all BFF replicas. It returns false if another holder has it.
// The returned function releases the lock only while this caller still owns it.
func (s *Store) TryLock(ctx context.Context, id string, ttl time.Duration) (func(context.Context), bool, error) {
	key, owner := lockKey(id), rand.Text()
	err := s.rdb.SetArgs(ctx, key, owner, redis.SetArgs{Mode: "NX", TTL: ttl}).Err()
	if errors.Is(err, redis.Nil) {
		return nil, false, nil
	}
	if err != nil {
		return nil, false, fmt.Errorf("session: lock: %w", err)
	}
	unlock := func(ctx context.Context) {
		// A failed unlock only delays the next refresh until the lock's TTL.
		_ = unlockScript.Run(ctx, s.rdb, []string{key}, owner).Err()
	}
	return unlock, true, nil
}
