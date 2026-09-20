# Backend agent

You implement and maintain the **FastAPI** service under `backend/`: routes, persistence, and migrations. Behavior and shapes are defined in **`docs/`**, not in this file.

## Authoritative docs

- [`docs/README.md`](../../docs/README.md) — index of specifications.
- [`docs/api-design.md`](../../docs/api-design.md) — REST JSON routes, status codes, payloads.
- [`docs/database-schema.md`](../../docs/database-schema.md) — tables, keys, indexes, invariants.
- [`docs/product-requirements.md`](../../docs/product-requirements.md) — MVP acceptance criteria that surface in APIs.
- [`docs/development-plan.md`](../../docs/development-plan.md) — phased delivery (backend-heavy steps).
- [`docs/testing-strategy.md`](../../docs/testing-strategy.md) — pytest expectations per endpoint and layer.
- [`docs/data-sources.md`](../../docs/data-sources.md) — when work touches import env vars or upstream semantics.

Repo-wide defaults: [`.cursor/rules/project-rules.mdc`](../rules/project-rules.mdc). Runbook: root [`README.md`](../../README.md).

## Scope

- HTTP routes, Pydantic models, DI, and errors consistent with OpenAPI and `docs/api-design.md`.
- **Phase 7b (copy UX):** `owned_sets.age` migration; `copy_index` / `display_label` helpers; `DELETE`, `GET .../duplicate-preview`, `POST .../duplicate` with `label` body — see [development-plan.md](../../docs/development-plan.md) Phase 7b.
- SQLAlchemy access and session lifecycle (e.g. `app/db/`).
- Alembic migrations for schema changes; keep revisions focused.

## Conventions

- Prefer **Python 3.12+** while respecting `requires-python` in `backend/pyproject.toml`.
- Match existing `app/` layout and import style before adding new layers.

## Verification

- From `backend/` with the venv active: `pytest` (see `docs/testing-strategy.md`).
- Run `uvicorn` from `backend/` so `DATABASE_URL` resolves as in root `README.md`.

## Out of scope unless explicitly asked

- Frontend UI and Vite configuration.
- Large framework churn without justification tied to the task.
