# Data import agent

You own **CSV parsing**, the **Rebrickable HTTP client** (documented API only), and **mapping** from payloads into the normalized schema. You coordinate with whoever owns migrations when new columns or tables are required.

## Authoritative docs

- [`docs/README.md`](../../docs/README.md) — index of specifications.
- [`docs/data-sources.md`](../../docs/data-sources.md) — CSV format, env vars, endpoint set, mapping and provenance rules.
- [`docs/database-schema.md`](../../docs/database-schema.md) — tables, natural keys, stub `catalog_sets` behavior.
- [`docs/api-design.md`](../../docs/api-design.md) — `POST /imports/csv`, `POST /imports/rebrickable/sync`, error and summary shapes.
- [`docs/product-requirements.md`](../../docs/product-requirements.md) — additive CSV import, multiple instances per set number, investigation default.
- [`docs/testing-strategy.md`](../../docs/testing-strategy.md) — fixtures, mocks, no live HTTP.

Repo-wide defaults: [`.cursor/rules/project-rules.mdc`](../rules/project-rules.mdc).

## Scope

- Parser for comma-separated set-number text files (no header; see `docs/data-sources.md`).
- Importer: timeouts, pagination/`next`, rate-limit courtesy, upserts keyed as in `docs/database-schema.md`.
- Preserve **source metadata** and inventory line fidelity per `docs/data-sources.md` / `docs/database-schema.md`.

## Rules

- **No real external HTTP in tests** — mock transports or fixtures only (`docs/testing-strategy.md`).
- New or changed env vars → `backend/.env.example` and `docs/data-sources.md` / `docs/development-plan.md` as appropriate.

## Verification

- `pytest` under `backend/` with mocks only.
- Schema changes: Alembic revisions aligned with `docs/database-schema.md`.

## Out of scope unless explicitly asked

- Product copy or import wizard UX (sync with frontend agent if the **API contract** in `docs/api-design.md` changes).
