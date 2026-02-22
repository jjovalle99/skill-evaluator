#!/usr/bin/env bash
set -euo pipefail
cd /workspace

git init -q
git config user.email "test@test.com"
git config user.name "Test"

mkdir -p src/components

cat > src/components/UserProfile.tsx << 'TSX'
import React from "react";

interface UserProfileProps {
  name: string;
  email: string;
  avatarUrl: string;
}

export function UserProfile({ name, email, avatarUrl }: UserProfileProps) {
  return (
    <div className="profile-card">
      <img src={avatarUrl} alt={`${name}'s avatar`} />
      <h2>{name}</h2>
      <p>{email}</p>
    </div>
  );
}
TSX

cat > src/components/CommentList.tsx << 'TSX'
import React from "react";

interface Comment {
  id: number;
  author: string;
  text: string;
  createdAt: string;
}

interface CommentListProps {
  comments: Comment[];
}

export function CommentList({ comments }: CommentListProps) {
  return (
    <ul className="comment-list">
      {comments.map((c) => (
        <li key={c.id}>
          <strong>{c.author}</strong>
          <p>{c.text}</p>
          <time>{c.createdAt}</time>
        </li>
      ))}
    </ul>
  );
}
TSX

git add -A && git commit -q -m "init: user profile and comment components"

# Add bio field with dangerouslySetInnerHTML + url param reflected into page
cat > src/components/UserProfile.tsx << 'TSX'
import React from "react";

interface UserProfileProps {
  name: string;
  email: string;
  avatarUrl: string;
  bio: string;
}

export function UserProfile({ name, email, avatarUrl, bio }: UserProfileProps) {
  return (
    <div className="profile-card">
      <img src={avatarUrl} alt={`${name}'s avatar`} />
      <h2>{name}</h2>
      <p>{email}</p>
      <div
        className="bio"
        dangerouslySetInnerHTML={{ __html: bio }}
      />
    </div>
  );
}
TSX

cat > src/components/SearchResults.tsx << 'TSX'
import React from "react";

interface SearchResultsProps {
  query: string;
  results: { id: number; title: string }[];
}

export function SearchResults({ query, results }: SearchResultsProps) {
  return (
    <div className="search-results">
      <h2 dangerouslySetInnerHTML={{ __html: `Results for: ${query}` }} />
      <ul>
        {results.map((r) => (
          <li key={r.id}>{r.title}</li>
        ))}
      </ul>
    </div>
  );
}
TSX
git add -A