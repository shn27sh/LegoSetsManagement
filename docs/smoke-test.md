# Local smoke test

A **sequential** check that the repo installs, tests pass, migrations apply, core API routes respond, and the frontend builds. Use this during development on any branch (including `main`).

This is **not** a substitute for the [**pre-submit**](../.cursor/agents/pre-submit.md) agent (spec review + full acceptance mapping before PRs). Smoke is faster and developer-oriented.

## Run

From the repository root:

```bash
./scripts/smoke.sh
```

Requirements: `python3`, `npm`, network for `pip` / `npm` on a clean machine.

## Steps (stop on first failure)

| Step | What it does |
|------|----------------|
| 1 | Create `backend/.venv` if missing; `pip install -r backend/requirements-dev.txt` |
| 2 | `pytest` in `backend/` |
| 3 | Fresh `backend/data/smoke.db`; `alembic upgrade head` with `DATABASE_URL` pointing at it |
| 4 | Probe `GET /health`, `POST /api/imports/csv`, and (when registered) `POST /api/imports/jobs` with poll until complete via [`scripts/smoke_app_probe.py`](../scripts/smoke_app_probe.py). Rebrickable is **mocked** in the probe (no live API). Step 3 must use a **fresh** `smoke.db` — the jobs probe re-imports the same fixture with `existing_set_mode=copy` after the synchronous CSV import. Older branches skip missing routes only. |
| 5 | `npm ci` in `frontend/` when `node_modules` is missing (or always when `FORCE_SMOKE_NPM=1`) |
| 6 | `npm test` in `frontend/` (Vitest unit tests) |
| 7 | `npm run build` in `frontend/` |

On failure the script exits non-zero and prints which step failed. **Fix the failure before re-running**; do not patch around a red step without understanding it.

## Optional flags / env

| Variable | Effect |
|----------|--------|
| `FORCE_SMOKE_NPM=1` | Re-run `npm ci` even if `frontend/node_modules` exists |

Step 4 expects a fresh database from step 3. To run the probe alone:

```bash
rm -f backend/data/smoke.db
cd backend && DATABASE_URL="sqlite:///$(pwd)/data/smoke.db" alembic upgrade head
DATABASE_URL="sqlite:///$(pwd)/data/smoke.db" python3 ../scripts/smoke_app_probe.py
```

## Cursor agent

To run the same flow from chat, invoke the [**smoke**](../.cursor/agents/smoke.md) agent. It executes `./scripts/smoke.sh` step by step and stops to explain the first error without refactoring or adding features.

## Related

- [ci.md](./ci.md) — GitHub Actions (pytest + frontend build; no live server)
- [testing-strategy.md](./testing-strategy.md) — full automated test plan
- [frontend-testing.md](./frontend-testing.md) — Vitest workflow during UI development
- [pre-submit agent](../.cursor/agents/pre-submit.md) — pre-PR gate
