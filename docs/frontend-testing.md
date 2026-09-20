# Frontend unit testing

The frontend uses **Vitest** and **React Testing Library** for unit and component tests. Tests run in **jsdom** (no browser required). They must **not** call the live backend or Rebrickable; mock HTTP with `fetch` stubs or [MSW](https://mswjs.io/) when UI starts calling APIs.

## Commands

From `frontend/`:

| Command | Purpose |
|---------|---------|
| `npm test` | Run all tests once (CI and pre-commit) |
| `npm run test:watch` | Re-run on file changes during development |

From the repository root, `./scripts/smoke.sh` runs `npm test` before `npm run build`.

## Layout

| Path | Role |
|------|------|
| `src/**/*.test.tsx` | Colocate tests next to components, or mirror `src/` structure |
| `src/test/setup.ts` | Global setup (`@testing-library/jest-dom`) |
| `vite.config.ts` | Vitest config (`environment: jsdom`, `setupFiles`) |

**Exclude** test files from the production TypeScript build via `tsconfig.app.json` `exclude`.

## What to test (MVP)

Detailed scenarios live in [testing-strategy.md](./testing-strategy.md#frontend-vitest--react-testing-library). Summary:

- **Present:** Vitest suites colocated with components (`*.test.tsx`) and utilities (`*.test.ts`) — sets list, set detail (incl. Part view), search, import, reports, Settings/app modes, PDF export helpers. See [testing-strategy.md](./testing-strategy.md) for the full table.
- **As features land:** add or extend colocated tests with mocked API JSON aligned to [api-design.md](./api-design.md).

## Development workflow

1. Implement or change a component under `frontend/src/`.
2. Add or update `*.test.tsx` in the same change when behavior is user-visible or branches on API data.
3. Run `npm run test:watch` while iterating, or `npm test` before commit.
4. Invoke the [**frontend**](../.cursor/agents/frontend.md) agent for UI work; [**qa**](../.cursor/agents/qa.md) for test coverage gaps.

## Mocking APIs

Until MSW is added, use `vi.stubGlobal("fetch", …)` or pass props from parent tests. Example pattern for a future list page:

```typescript
vi.stubGlobal(
  "fetch",
  vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ items: [], total: 0 }),
  } as Response),
);
```

Prefer small fixtures under `frontend/src/test/fixtures/` (create when the first API-backed component ships).

## CI

GitHub Actions runs `npm test` then `npm run build` in the frontend job. See [ci.md](./ci.md).

## Related

- [testing-strategy.md](./testing-strategy.md) — full test plan (backend + frontend)
- [smoke-test.md](./smoke-test.md) — local smoke script
- [frontend agent](../.cursor/agents/frontend.md) — UI implementation + tests in the same change
