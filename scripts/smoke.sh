#!/usr/bin/env bash
# Local development smoke test — runs one step at a time; stops on first failure.
# See docs/smoke-test.md and .cursor/agents/smoke.md

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"
SMOKE_DB="$BACKEND/data/smoke.db"
DATABASE_URL="sqlite:///${SMOKE_DB}"

step() {
  echo ""
  echo "================================================================"
  echo "Step $1: $2"
  echo "================================================================"
}

fail() {
  echo ""
  echo "SMOKE TEST FAILED at step $1: $2" >&2
  exit 1
}

# --- Step 1: Backend dependencies ---
step 1 "Backend install / check dependencies"
if [[ ! -d "$VENV" ]]; then
  echo "Creating virtualenv at $VENV"
  python3 -m venv "$VENV"
fi
# shellcheck source=/dev/null
source "$VENV/bin/activate"
python -m pip install --upgrade pip -q
pip install -r "$BACKEND/requirements-dev.txt"
echo "Backend dependencies OK"

# --- Step 2: Backend pytest ---
step 2 "Run backend pytest"
cd "$BACKEND"
if ! pytest -q; then
  fail 2 "pytest reported failures (see output above)"
fi
echo "pytest OK"

# --- Step 3: Alembic migrate ---
step 3 "Run alembic upgrade head"
mkdir -p "$BACKEND/data"
rm -f "$SMOKE_DB"
export DATABASE_URL
if ! alembic upgrade head; then
  fail 3 "alembic upgrade head failed (see output above)"
fi
echo "alembic upgrade head OK (database: $SMOKE_DB)"

# --- Step 4: FastAPI health + CSV import probe ---
step 4 "Verify GET /health and POST /api/imports/csv"
if ! DATABASE_URL="$DATABASE_URL" python "$ROOT/scripts/smoke_app_probe.py"; then
  fail 4 "application probe failed (see output above)"
fi
echo "Application probe OK"

# --- Step 5: Frontend dependencies ---
step 5 "Frontend npm install (if needed)"
cd "$FRONTEND"
if [[ "${FORCE_SMOKE_NPM:-}" == "1" ]] || [[ ! -d node_modules ]]; then
  if [[ -f package-lock.json ]]; then
    npm ci
  else
    npm install
  fi
  echo "Frontend dependencies installed"
else
  echo "node_modules present; skipping install (set FORCE_SMOKE_NPM=1 to reinstall)"
fi

# --- Step 6: Frontend unit tests ---
step 6 "Run frontend npm test"
if ! npm test; then
  fail 6 "npm test failed (see output above)"
fi
echo "frontend tests OK"

# --- Step 7: Frontend production build ---
step 7 "Run frontend npm run build"
if ! npm run build; then
  fail 7 "npm run build failed (see output above)"
fi
echo "frontend build OK"

echo ""
echo "================================================================"
echo "SMOKE TEST PASSED (all steps)"
echo "================================================================"
