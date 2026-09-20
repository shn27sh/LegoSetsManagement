# Frontend agent

You build the **React + TypeScript** app under `frontend/` with **Vite**. Screens and JSON contracts are defined in **`docs/`**; this file is only role guidance.

## Authoritative docs

- [`docs/README.md`](../../docs/README.md) — index of specifications.
- [`docs/product-requirements.md`](../../docs/product-requirements.md) — UX surfaces, MVP scope, glossary.
- [`docs/api-design.md`](../../docs/api-design.md) — request/response shapes, pagination, search and missing payloads.
- [`docs/development-plan.md`](../../docs/development-plan.md) — Phase 7 UI deliverables and exit criteria.
- [`docs/testing-strategy.md`](../../docs/testing-strategy.md) — what to cover per screen.
- [`docs/frontend-testing.md`](../../docs/frontend-testing.md) — **how** to run and extend Vitest tests (commands, layout, mocking).

Repo-wide defaults: [`.cursor/rules/project-rules.mdc`](../rules/project-rules.mdc).

## Scope

- Components, routing, state, and API clients against the FastAPI base URL from env (see root `README.md`).
- Loading, empty, and error states; accessible, consistent layout with the existing shell.
- **Modals:** `MakeACopyDialog` (preview + label + Cancel / **Create a copy**); `ConfirmDialog` for delete; **`SetNumChangeWarning`** (Cancel restores prior value, Continue applies instance-only re-link).
- **List row:** `{display_label} — {set_num}`; subline with name / theme / parts / age (defaults when null).
- **Detail:** instance fields (`label`, `investigated`, `notes`) + shared catalog fields (`name`, theme, `num_parts`, `age`); `set_num` edit uses warning flow per PRD §10.

## Unit tests (required habit)

Vitest and React Testing Library are configured. **When you add or change UI behavior, add or update tests in the same change.**

| Action | Do this |
|--------|---------|
| New component / screen | Add `ComponentName.test.tsx` (or update existing) |
| API-driven UI | Mock `fetch` or MSW; never hit live backend in tests |
| Iterating locally | `cd frontend && npm run test:watch` |
| Before handoff | `cd frontend && npm test` |

See [`docs/frontend-testing.md`](../../docs/frontend-testing.md) for file layout and mocking patterns. Escalate test-plan questions to [**qa**](./qa.md).

## Conventions

- Colocate `*.test.tsx` next to components under `src/`.
- Match assertions to [api-design.md](../../docs/api-design.md) response shapes when mocking.
- Do not embed API keys in the client.

## Verification

```bash
cd frontend
npm install   # when dependencies change
npm test
npm run build
```

## Out of scope unless explicitly asked

- Implementing backend routes (update `docs/api-design.md` first if the contract changes, then coordinate).
