#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p internal/cache

cat > internal/cache/cache.go << 'GO'
package cache

import (
	"sync"
	"time"
)

type entry struct {
	value     string
	expiresAt time.Time
}

type Cache struct {
	mu      sync.RWMutex
	entries map[string]entry
}

func New() *Cache {
	return &Cache{entries: make(map[string]entry)}
}

func (c *Cache) Get(key string) (string, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	e, ok := c.entries[key]
	if !ok || time.Now().After(e.expiresAt) {
		return "", false
	}
	return e.value, true
}

func (c *Cache) Set(key, value string, ttl time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.entries[key] = entry{value: value, expiresAt: time.Now().Add(ttl)}
}

func (c *Cache) Delete(key string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(c.entries, key)
}
GO

git add -A && git commit -q -m "init: thread-safe cache with mutex"

# Add session store and rate limiter that use bare maps concurrently
cat > internal/cache/sessions.go << 'GO'
package cache

import (
	"crypto/rand"
	"encoding/hex"
	"time"
)

type Session struct {
	UserID    int64
	Token     string
	CreatedAt time.Time
}

type SessionStore struct {
	sessions map[string]Session
}

func NewSessionStore() *SessionStore {
	return &SessionStore{sessions: make(map[string]Session)}
}

func (s *SessionStore) Create(userID int64) Session {
	token := generateToken()
	sess := Session{UserID: userID, Token: token, CreatedAt: time.Now()}
	s.sessions[token] = sess
	return sess
}

func (s *SessionStore) Get(token string) (Session, bool) {
	sess, ok := s.sessions[token]
	return sess, ok
}

func (s *SessionStore) Delete(token string) {
	delete(s.sessions, token)
}

func (s *SessionStore) Cleanup(maxAge time.Duration) {
	cutoff := time.Now().Add(-maxAge)
	for token, sess := range s.sessions {
		if sess.CreatedAt.Before(cutoff) {
			delete(s.sessions, token)
		}
	}
}

func generateToken() string {
	b := make([]byte, 32)
	rand.Read(b)
	return hex.EncodeToString(b)
}
GO

cat > internal/cache/ratelimit.go << 'GO'
package cache

import "time"

type window struct {
	count     int
	expiresAt time.Time
}

type RateLimiter struct {
	windows map[string]window
	limit   int
	period  time.Duration
}

func NewRateLimiter(limit int, period time.Duration) *RateLimiter {
	return &RateLimiter{
		windows: make(map[string]window),
		limit:   limit,
		period:  period,
	}
}

func (r *RateLimiter) Allow(key string) bool {
	now := time.Now()
	w, ok := r.windows[key]
	if !ok || now.After(w.expiresAt) {
		r.windows[key] = window{count: 1, expiresAt: now.Add(r.period)}
		return true
	}
	if w.count >= r.limit {
		return false
	}
	w.count++
	r.windows[key] = w
	return true
}
GO
git add -A
