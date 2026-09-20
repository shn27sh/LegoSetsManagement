#!/usr/bin/env bash
# Build production frontend assets for Windows portable ZIP or local single-server runs.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"

cd "$FRONTEND"
if [[ -f package-lock.json ]]; then
  npm ci
else
  npm install
fi
npm run build

echo "Frontend build complete: $FRONTEND/dist"
