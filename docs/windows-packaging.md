# Windows portable ZIP packaging

This document describes how to build and distribute the **portable Windows ZIP** for non-technical users. Development remains on Linux; Windows builds use a Windows machine or GitHub Actions (`windows-latest`).

## What the user gets

After unzipping:

```
LEGO-Collection-Manager-<version>-win64/
  Launch LEGO Collection Manager.bat
  lcm-server/              # PyInstaller one-folder bundle (lcm-server.exe)
  web/                     # production frontend (Vite build)
  data/                    # SQLite DB and logs (created on first run)
  config.env.example
  README.txt
```

Double-click the `.bat` file → server starts → browser opens `http://127.0.0.1:8000/`.

## Architecture

- One process: `lcm-server.exe` runs FastAPI + static UI ([`backend/run_server.py`](../backend/run_server.py)).
- Paths resolve via [`backend/app/runtime_paths.py`](../backend/app/runtime_paths.py) using `LCM_INSTALL_ROOT` (set by the launcher to the ZIP root).
- Database migrations run automatically on startup ([`backend/app/db/migration_ops.py`](../backend/app/db/migration_ops.py)).
- Rebrickable API key: copy `config.env.example` → `config.env` and edit (see README.txt).

## Phase 1 — Manual build

### Step A — Frontend (Linux or Windows)

```bash
./scripts/build-frontend.sh
```

Output: [`frontend/dist/`](../frontend/dist/).

### Step B — Server bundle (Windows only)

On a Windows PC or VM with **Python 3.12+**:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements-packaging.txt
pyinstaller pyinstaller.spec
```

Output: `backend\dist\lcm-server\lcm-server.exe`.

### Step C — Assemble ZIP (Windows)

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows/assemble-portable.ps1 -Version 0.1.0
```

Output: `dist\windows-portable\LEGO-Collection-Manager-0.1.0-win64.zip`.

### Local test without Windows (Linux dev)

You can verify production mode on Linux:

```bash
./scripts/build-frontend.sh
cd backend
source .venv/bin/activate
export LCM_INSTALL_ROOT="$(cd .. && pwd)"
export LCM_WEB_ROOT="$LCM_INSTALL_ROOT/frontend/dist"
python run_server.py
```

Open http://127.0.0.1:8000/ — same code path as the Windows bundle (minus PyInstaller).

## Phase 2 — GitHub Actions release

See [`.github/workflows/release-windows.yml`](../.github/workflows/release-windows.yml). Trigger:

- Push a tag `v*` (for example `v0.1.0`), or
- **workflow_dispatch** with a version string.

Download the ZIP from:

- **GitHub Releases** (when you pushed a `v*` tag) — attached to the release, or
- **Actions → Release Windows portable ZIP → Artifacts** (`lego-collection-manager-windows-portable`)

The file `backend/pyinstaller.spec` must be committed (it is exempted from `*.spec` in `.gitignore`). If the workflow reports “Spec file not found”, the spec was missing from the repository at that tag.

## Upgrading

1. Download the new ZIP and extract to a new folder.
2. Copy the previous folder’s **`data/`** directory (and **`config.env`** if present) into the new folder.
3. Run the launcher `.bat` again.

Do not replace `data/` with an empty folder unless you intend to start a fresh collection.

## Phase 3 — Installer (planned)

A future **Inno Setup** or **NSIS** installer may:

- Install under `%LOCALAPPDATA%\Programs\LEGOCollectionManager`
- Add a Start Menu shortcut
- Optionally code-sign the executable to reduce SmartScreen warnings

See the project plan; not implemented in Phase 1–2.

## Troubleshooting builds

| Issue | Action |
|-------|--------|
| PyInstaller import errors | Add missing modules to `hiddenimports` in [`backend/pyinstaller.spec`](../backend/pyinstaller.spec) |
| Alembic not found at runtime | Confirm `alembic.ini` and `alembic/` are listed in `datas` in the spec |
| Blank UI | Ensure `web/` contains `index.html` and `assets/` from `npm run build` |
| Antivirus quarantine | Expected for unsigned exes; allowlist or plan Phase 3 signing |

## Related files

| File | Purpose |
|------|---------|
| [`scripts/build-frontend.sh`](../scripts/build-frontend.sh) | Production frontend build |
| [`scripts/windows/Launch.bat`](../scripts/windows/Launch.bat) | User launcher template |
| [`scripts/windows/assemble-portable.ps1`](../scripts/windows/assemble-portable.ps1) | ZIP assembly |
| [`backend/pyinstaller.spec`](../backend/pyinstaller.spec) | PyInstaller configuration |
| [`backend/requirements-packaging.txt`](../backend/requirements-packaging.txt) | Windows build dependencies |
