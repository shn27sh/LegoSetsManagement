# Cursor agent briefs

Contributor roles for this repository. Each brief links to authoritative specs under [`docs/`](../../docs/); specs are **not** duplicated here.

| Agent | Use when |
|-------|----------|
| [architect.md](./architect.md) | Cross-cutting design, spec alignment, phased delivery |
| [backend.md](./backend.md) | FastAPI routes, SQLAlchemy, Alembic |
| [frontend.md](./frontend.md) | React + Vite UI + Vitest tests in the same change |
| [data-import.md](./data-import.md) | CSV text import, Rebrickable client |
| [docs.md](./docs.md) | README, `docs/`, `.env.example` |
| [qa.md](./qa.md) | Writing/updating automated tests |
| [smoke.md](./smoke.md) | **During development:** local smoke test (`./scripts/smoke.sh`) |
| [ci.md](./ci.md) | GitHub Actions workflow |
| [pre-submit.md](./pre-submit.md) | **Before commit/PR:** doc consistency + CI + smoke/acceptance gate |

**Recommended habit:** run the **pre-submit** agent after any doc or code change you plan to submit.
