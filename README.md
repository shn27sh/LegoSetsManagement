# LEGO Collection Manager

Local-first LEGO collection manager (MVP in progress). This repository contains a **FastAPI** backend, a **React + Vite** frontend, and product documentation under `docs/`.

## Prerequisites

- **Python 3.10+** (installable range in `backend/pyproject.toml`). **Python 3.12+** is the target in [`.cursor/rules/project-rules.mdc`](.cursor/rules/project-rules.mdc); use 3.12 when you can.
- **Node.js** 20+ and npm (for the frontend)

## Backend

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

If `pip install -e ".[dev]"` fails (for example, build tooling issues), install dependencies directly:

```bash
pip install -r requirements-dev.txt
```

Then:

```bash
cp .env.example .env        # optional; defaults match .env.example
mkdir -p data
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **Health check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) returns `{"status":"ok"}`.
- **API docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) (OpenAPI).

**Backend APIs** (CSV import, Rebrickable sync, set copies (`/owned-sets`), search, missing parts, reports (`/reports/*`), local images including **`GET /api/elements/{element_id}/image`**) and the **React MVP UI** (sets list, set detail, search, import, reports, Settings) are implemented. LEGO **Element IDs** are stored once per colored part (part alias class + color) in **`part_color_keys`** / **`part_color_element_ids`**, so the same part + color shows the same Element IDs in every set.

**App modes:** View (default), Investigate, and Edit are selected on **`/settings`** and persisted in browser `localStorage` (`lcm.appMode`). View/Investigate gate mutations in the UI; Edit enables full editing.

Configuration is read from the environment (see [`backend/.env.example`](backend/.env.example)). Run Alembic and uvicorn from `backend/` so relative paths resolve under `backend/data/`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `sqlite:///./data/lego.db` | SQLite database file → `backend/data/lego.db` |
| `REBRICKABLE_API_KEY` | — | Required for Rebrickable sync (not for tests) |
| `LOG_LEVEL` | `WARNING` | Importer and application log verbosity |
| `LOG_FILE_PATH` | `./data/server.log` | Local rotating server log file; `*.log` files are ignored by git |
| `IMPORT_FAILURE_LOG_PATH` | `./data/import_failures.log` | Dedicated JSON-lines text file for failed imports/syncs/image downloads |
| `ELEMENTS_CSV_PATH` | `../data/elements.csv` | Optional Rebrickable Element ID mapping used during import/sync enrichment |
| `THEMES_CSV_PATH` | `../data/themes.csv` | Optional Rebrickable theme mapping used to display parent themes during import/sync |
| `AGE_CSV_PATH` | `../data/age.csv` | Optional local age mapping used by the Import page metadata update |
| `SETS_CSV_PATH` | `../data/sets.csv` | Optional Rebrickable set catalog CSV used by the Import page metadata update |

User-uploaded and sync-downloaded **part**, **element** (color-specific), **set**, and **minifigure** images are stored as JPEG/PNG BLOBs in SQLite (see [docs/data-sources.md](docs/data-sources.md)); no upload directory is required.

On startup the API **refuses to start** unless the database is at the latest Alembic revision (`alembic upgrade head`). Importers log structured summaries (set counts, failures) to console and the local log file, write failed imports/syncs to the dedicated failure log, and never log API keys.

### Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Then open the URL printed by Vite (typically [http://127.0.0.1:5173](http://127.0.0.1:5173)). The dev server proxies `/api` to the backend on port 8000 — start **uvicorn** in `backend/` first.

Optional: set `VITE_API_BASE_URL` (default `/api`) if the API is hosted elsewhere.

```bash
npm test        # Vitest unit tests (see docs/frontend-testing.md)
npm run build   # production build
```

## Continuous integration

On **GitHub**, every **push** and **pull request** runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml): backend **`pytest`**, frontend **`npm test`**, and **`npm run build`**. Details and local parity commands are in [`docs/ci.md`](docs/ci.md).

For a broader local check (install, tests, migration, API probe, frontend build), run from the repository root:

```bash
./scripts/smoke.sh
```

See [`docs/smoke-test.md`](docs/smoke-test.md).

## Sample data

Example LEGO set numbers for CSV import experiments live in [`data/sample_sets.csv`](data/sample_sets.csv).

## Windows portable ZIP

Non-technical users can run a **portable ZIP** on Windows (no Python/Node install). Build instructions, upgrade path, and troubleshooting are in [`docs/windows-packaging.md`](docs/windows-packaging.md). Validate a build with [`docs/windows-smoke-test.md`](docs/windows-smoke-test.md).

### Release a new Windows portable ZIP

**Recommended — GitHub Actions** (builds on `windows-latest`; no local Windows machine required):

```bash
# From the repository root — run the same checks CI uses before tagging
./scripts/smoke.sh

# Tag and push (version in the tag becomes the ZIP name, e.g. v0.1.0 → …-0.1.0-win64.zip)
git tag v0.1.0
git push origin v0.1.0
```

The workflow [`.github/workflows/release-windows.yml`](.github/workflows/release-windows.yml) runs automatically on `v*` tags. Download the ZIP from **GitHub Releases** (attached to the release).

To build without a tag, use **Actions → Release Windows portable ZIP → Run workflow** and enter a version string (for example `0.1.0`). Download the artifact **`lego-collection-manager-windows-portable`** from the workflow run.

**Manual build on a Windows PC** (same output as CI; useful for local debugging):

```powershell
# Step A — frontend (from repo root)
cd frontend
npm ci
npm run build
cd ..

# Step B — PyInstaller server bundle
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-packaging.txt
pyinstaller pyinstaller.spec
cd ..

# Step C — assemble ZIP
powershell -ExecutionPolicy Bypass -File scripts/windows/assemble-portable.ps1 -Version 0.1.0
```

On Linux or macOS, Step A can use `./scripts/build-frontend.sh` instead; Steps B and C still require Windows.

Output: `dist\windows-portable\LEGO-Collection-Manager-0.1.0-win64.zip`.

## Documentation

Product and technical specs are in [`docs/`](docs/). Use [`docs/README.md`](docs/README.md) as an index of each specification file.

During development, use the [**smoke** agent](.cursor/agents/smoke.md) or `./scripts/smoke.sh` for a quick health check. Before committing or opening a PR, use the [**pre-submit** agent](.cursor/agents/pre-submit.md) for doc consistency and CI/acceptance review.
