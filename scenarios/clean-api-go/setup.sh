#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p internal/api internal/store

cat > go.mod << 'GOMOD'
module example.com/clean-api

go 1.22
GOMOD

cat > internal/store/repository.go << 'GO'
package store

import "context"

type User struct {
	ID    int64
	Name  string
	Email string
}

type UserRepository interface {
	SearchByEmail(ctx context.Context, emailPrefix string) ([]User, error)
}
GO

cat > internal/api/server.go << 'GO'
package api

import "net/http"

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

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}
GO

git add -A && git commit -q -m "init: health endpoint and repository contract"

# Add clean user-search endpoint with validation and safe SQL query handling
cat > internal/store/sql_repository.go << 'GO'
package store

import (
	"context"
	"database/sql"
)

type SQLUserRepository struct {
	db *sql.DB
}

func NewSQLUserRepository(db *sql.DB) *SQLUserRepository {
	return &SQLUserRepository{db: db}
}

func (r *SQLUserRepository) SearchByEmail(ctx context.Context, emailPrefix string) ([]User, error) {
	rows, err := r.db.QueryContext(
		ctx,
		"SELECT id, name, email FROM users WHERE email LIKE ? ORDER BY id LIMIT 50",
		emailPrefix+"%",
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	users := make([]User, 0, 50)
	for rows.Next() {
		var user User
		if err := rows.Scan(&user.ID, &user.Name, &user.Email); err != nil {
			return nil, err
		}
		users = append(users, user)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	return users, nil
}
GO

cat > internal/api/users.go << 'GO'
package api

import (
	"encoding/json"
	"net/http"
	"regexp"

	"example.com/clean-api/internal/store"
)

var emailPrefixPattern = regexp.MustCompile(`^[a-zA-Z0-9.+\-@]{1,80}$`)

type UserSearchHandler struct {
	repo store.UserRepository
}

func NewUserSearchHandler(repo store.UserRepository) *UserSearchHandler {
	return &UserSearchHandler{repo: repo}
}

func (h *UserSearchHandler) Handle(w http.ResponseWriter, r *http.Request) {
	query := r.URL.Query().Get("email_prefix")
	if query == "" || !emailPrefixPattern.MatchString(query) {
		http.Error(w, "invalid email_prefix", http.StatusBadRequest)
		return
	}

	users, err := h.repo.SearchByEmail(r.Context(), query)
	if err != nil {
		http.Error(w, "database error", http.StatusInternalServerError)
		return
	}

	data, err := json.Marshal(users)
	if err != nil {
		http.Error(w, "encode error", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write(data)
}
GO

cat > internal/api/server.go << 'GO'
package api

import (
	"database/sql"
	"net/http"

	"example.com/clean-api/internal/store"
)

type Server struct {
	mux *http.ServeMux
}

func New(db *sql.DB) *Server {
	s := &Server{mux: http.NewServeMux()}
	s.mux.HandleFunc("GET /health", s.handleHealth)
	repo := store.NewSQLUserRepository(db)
	userHandler := NewUserSearchHandler(repo)
	s.mux.HandleFunc("GET /users", userHandler.Handle)
	return s
}

func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.mux.ServeHTTP(w, r)
}

func (s *Server) handleHealth(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}
GO

git add -A
