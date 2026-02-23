#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p internal/state

cat > go.mod << 'GOMOD'
module example.com/state-store

go 1.22
GOMOD

cat > internal/state/store.go << 'GO'
package state

import (
	"encoding/json"
	"os"
)

type Snapshot struct {
	Version int               `json:"version"`
	Values  map[string]string `json:"values"`
}

func PersistSnapshot(path string, snapshot Snapshot) error {
	payload, err := json.Marshal(snapshot)
	if err != nil {
		return err
	}

	tmpPath := path + ".tmp"
	if err := os.WriteFile(tmpPath, payload, 0o600); err != nil {
		return err
	}

	if err := os.Rename(tmpPath, path); err != nil {
		return err
	}

	return nil
}
GO

git add -A && git commit -q -m "init: snapshot persistence with strict error checks"

# Introduce ignored file-write error and nil error return on failure path
cat > internal/state/store.go << 'GO'
package state

import (
	"encoding/json"
	"os"
)

type Snapshot struct {
	Version int               `json:"version"`
	Values  map[string]string `json:"values"`
}

func PersistSnapshot(path string, snapshot Snapshot) error {
	payload, err := json.Marshal(snapshot)
	if err != nil {
		return err
	}

	tmpPath := path + ".tmp"
	_ = os.WriteFile(tmpPath, payload, 0o600)

	if err := os.Rename(tmpPath, path); err != nil {
		return nil
	}

	return nil
}
GO

git add -A
