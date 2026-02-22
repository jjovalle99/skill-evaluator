#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p internal/api

cat > internal/api/server.go << 'GO'
package api

import (
	"encoding/json"
	"net/http"
)

type Server struct {
	mux *http.ServeMux
}

func New() *Server {
	s := &Server{mux: http.NewServeMux()}
	s.mux.HandleFunc("GET /health", s.handleHealth)
	return s
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
GO

cat > go.mod << 'GOMOD'
module example.com/app

go 1.22
GOMOD

git add -A && git commit -q -m "init: http server with health endpoint"

# Clean feature: add a well-structured bookmark CRUD endpoint
cat > internal/api/bookmarks.go << 'GO'
package api

import (
	"encoding/json"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

type Bookmark struct {
	ID        int64     `json:"id"`
	URL       string    `json:"url"`
	Title     string    `json:"title"`
	CreatedAt time.Time `json:"created_at"`
}

type BookmarkStore struct {
	mu    sync.RWMutex
	items map[int64]Bookmark
	seq   atomic.Int64
}

func NewBookmarkStore() *BookmarkStore {
	return &BookmarkStore{items: make(map[int64]Bookmark)}
}

func (bs *BookmarkStore) Create(url, title string) Bookmark {
	id := bs.seq.Add(1)
	b := Bookmark{ID: id, URL: url, Title: title, CreatedAt: time.Now()}
	bs.mu.Lock()
	bs.items[id] = b
	bs.mu.Unlock()
	return b
}

func (bs *BookmarkStore) List() []Bookmark {
	bs.mu.RLock()
	defer bs.mu.RUnlock()
	out := make([]Bookmark, 0, len(bs.items))
	for _, b := range bs.items {
		out = append(out, b)
	}
	return out
}

func RegisterBookmarkRoutes(mux *http.ServeMux, store *BookmarkStore) {
	mux.HandleFunc("GET /bookmarks", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, store.List())
	})

	mux.HandleFunc("POST /bookmarks", func(w http.ResponseWriter, r *http.Request) {
		var input struct {
			URL   string `json:"url"`
			Title string `json:"title"`
		}
		if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "invalid json"})
			return
		}
		if input.URL == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "url is required"})
			return
		}
		b := store.Create(input.URL, input.Title)
		writeJSON(w, http.StatusCreated, b)
	})
}
GO

# Wire the new routes into the server
cat > internal/api/server.go << 'GO'
package api

import (
	"encoding/json"
	"net/http"
)

type Server struct {
	mux *http.ServeMux
}

func New() *Server {
	s := &Server{mux: http.NewServeMux()}
	s.mux.HandleFunc("GET /health", s.handleHealth)
	store := NewBookmarkStore()
	RegisterBookmarkRoutes(s.mux, store)
	return s
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}
GO
git add -A
