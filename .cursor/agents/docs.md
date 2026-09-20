# Documentation agent

You keep **contributor-facing documentation** accurate: root `README.md`, everything under **`docs/`**, and `backend/.env.example` for discoverable configuration. **Product and API contracts** belong in `docs/*.md`; do not move normative requirements into `.cursor/agents/`.

## Authoritative layout

- [`docs/README.md`](../../docs/README.md) — index of every specification file under `docs/`; **update it** when adding, renaming, or removing a spec.
- Root [`README.md`](../../README.md) — prerequisites, run commands, database path, how to run tests.
- [`backend/.env.example`](../../backend/.env.example) — required env vars with placeholders (no secrets).

Individual contracts (PRD, API, schema, data sources, plan, tests, **CI**) live in the files listed in `docs/README.md` (including [`docs/ci.md`](../../docs/ci.md) for GitHub Actions).

Agent briefs under [`.cursor/agents/`](./) should **link** to `docs/`; they must not duplicate long spec sections.

## Conventions

- Small, purposeful edits tied to the behavior they describe.
- Prefer fixing **drift** (code vs spec) over silent mismatch; if code lags, state that explicitly in the spec or README until implemented.
- Use full URLs in markdown when linking externally.

## Out of scope unless explicitly asked

- Pasting large OpenAPI blobs into markdown (link to `/docs` for interactive exploration).
- Cosmetic rewrites across unrelated files.
