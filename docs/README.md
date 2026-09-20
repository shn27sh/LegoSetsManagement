# Specification index — LEGO Collection Manager

This folder holds the **authoritative product and technical contracts** for the MVP: requirements, API shapes, schema, data sources, delivery plan, and testing approach.

| Document | Role |
|----------|------|
| [product-requirements.md](./product-requirements.md) | Problem, user, scope, acceptance criteria, glossary (multi-instance ownership, duplicate instance, investigation flag, local missing-part photos) |
| [api-design.md](./api-design.md) | REST JSON routes, payloads, errors, pagination |
| [database-schema.md](./database-schema.md) | SQLite tables, keys, indexes, invariants |
| [data-sources.md](./data-sources.md) | CSV format, Rebrickable usage, mapping and provenance |
| [development-plan.md](./development-plan.md) | Phased delivery: MVP (Phases 1–8), post-MVP **9–18** (through Settings/app modes); Phase 14 sync UX with deferred backlog |
| [testing-strategy.md](./testing-strategy.md) | pytest / Vitest expectations, fixtures, no live APIs |
| [frontend-testing.md](./frontend-testing.md) | Vitest commands, layout, mocking, dev workflow |
| [smoke-test.md](./smoke-test.md) | Local dev smoke test (`./scripts/smoke.sh`) |
| [ci.md](./ci.md) | GitHub Actions: push/PR checks (backend pytest, frontend Vitest + build) |
| [windows-packaging.md](./windows-packaging.md) | Portable Windows ZIP build, install, and upgrade |
| [windows-portable-checklist.md](./windows-portable-checklist.md) | What the ZIP must contain; repo + user requirements |
| [windows-smoke-test.md](./windows-smoke-test.md) | Manual checklist for validating a Windows ZIP build |

Repository-wide **engineering defaults** (preferred stack, “no live API in tests”, etc.) live in [`.cursor/rules/project-rules.mdc`](../.cursor/rules/project-rules.mdc).

Cursor **agent briefs** under [`.cursor/agents/`](../.cursor/agents/) describe *contributor roles* (what to optimize for, where to look first). They **link** here; they do **not** replace these specifications. During development, use the [**smoke**](../.cursor/agents/smoke.md) agent or [`./scripts/smoke.sh`](../scripts/smoke.sh). Before you commit or open a PR, use the [**pre-submit**](../.cursor/agents/pre-submit.md) agent to review doc consistency and run CI/acceptance checks.
