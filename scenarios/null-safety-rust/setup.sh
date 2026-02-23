#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p src

cat > Cargo.toml << 'TOML'
[package]
name = "profile-render"
version = "0.1.0"
edition = "2021"
TOML

cat > src/lib.rs << 'RUST'
pub struct UserProfile {
    pub username: String,
    pub bio: Option<String>,
}

pub fn format_profile(profile: &UserProfile, include_label: bool) -> String {
    let bio = profile.bio.as_deref().unwrap_or("(empty)");
    if include_label {
        format!("Bio: {bio}")
    } else {
        bio.to_string()
    }
}
RUST

git add -A && git commit -q -m "init: safe profile formatting"

# Add inconsistent Option handling with unsafe unwrap path
cat > src/lib.rs << 'RUST'
pub struct UserProfile {
    pub username: String,
    pub bio: Option<String>,
}

pub fn format_profile(profile: &UserProfile, include_label: bool) -> String {
    if include_label {
        match profile.bio.as_ref() {
            Some(bio) => format!("Bio: {bio}"),
            None => "Bio: (empty)".to_string(),
        }
    } else {
        profile.bio.as_ref().unwrap().to_string()
    }
}
RUST

git add -A
