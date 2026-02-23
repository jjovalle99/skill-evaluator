#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p src

cat > Cargo.toml << 'TOML'
[package]
name = "config-parser"
version = "0.1.0"
edition = "2021"
TOML

cat > src/lib.rs << 'RUST'
use std::collections::HashMap;

pub struct Config {
    entries: HashMap<String, String>,
}

impl Config {
    pub fn new() -> Self {
        Config {
            entries: HashMap::new(),
        }
    }

    pub fn set(&mut self, key: &str, value: &str) {
        self.entries.insert(key.to_string(), value.to_string());
    }

    pub fn get(&self, key: &str) -> Option<&str> {
        self.entries.get(key).map(|v| v.as_str())
    }

    pub fn get_or_default<'a>(&'a self, key: &str, default: &'a str) -> &'a str {
        self.entries.get(key).map(|v| v.as_str()).unwrap_or(default)
    }
}
RUST

git add -A && git commit -q -m "init: safe config parser"

# Add three new methods with issues at different severity levels
cat > src/lib.rs << 'RUST'
use std::collections::HashMap;

pub struct Config {
    entries: HashMap<String, String>,
}

impl Config {
    pub fn new() -> Self {
        Config {
            entries: HashMap::new(),
        }
    }

    pub fn set(&mut self, key: &str, value: &str) {
        self.entries.insert(key.to_string(), value.to_string());
    }

    pub fn get(&self, key: &str) -> Option<&str> {
        self.entries.get(key).map(|v| v.as_str())
    }

    pub fn get_or_default(&self, key: &str, default: &str) -> String {
        self.entries.get(key).map(|v| v.as_str()).unwrap_or(default).to_string()
    }

    pub fn get_raw_ptr(&self, key: &str) -> *const u8 {
        let value = self.entries.get(key).cloned().unwrap_or_default();
        value.as_ptr()
    }

    pub fn require(&self, key: &str) -> &str {
        self.entries.get(key).map(|v| v.as_str()).unwrap()
    }
}
RUST
git add -A
