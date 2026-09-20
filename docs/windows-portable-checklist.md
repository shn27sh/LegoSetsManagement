# Windows portable ZIP — completeness checklist

Use this list to confirm the self-contained ZIP includes everything a Windows user needs (no Python, Node, or other installs).

## Inside the ZIP (required layout)

| Path | Purpose |
|------|---------|
| `Launch LEGO Collection Manager.bat` | Starts server + opens browser |
| `lcm-server/lcm-server.exe` | Backend (embedded Python + FastAPI + Alembic) |
| `web/index.html` (+ `web/assets/`) | Production React UI |
| `data/` | SQLite database and logs (writable) |
| `config.env.example` | Optional Rebrickable key / port |
| `README.txt` | User instructions |

## Not required on the user's PC

- Python, Node.js, npm, pip, uvicorn, or Vite
- A separate web server (IIS, nginx, etc.)
- Git

## Still required from the user

- **Windows 10/11** (64-bit)
- A **web browser** (Edge, Chrome, Firefox, …)
- **Unzip** the archive (built-in Windows “Extract All”)
- Optional: **Rebrickable API key** in `config.env` for online sync only

## Repository requirements (for GitHub to build the ZIP)

| Item | Location |
|------|----------|
| PyInstaller spec (must be in git) | [`backend/pyinstaller.spec`](../backend/pyinstaller.spec) |
| Release workflow | [`.github/workflows/release-windows.yml`](../.github/workflows/release-windows.yml) |
| Assemble script | [`scripts/windows/assemble-portable.ps1`](../scripts/windows/assemble-portable.ps1) |
| Launcher | [`scripts/windows/Launch.bat`](../scripts/windows/Launch.bat) |

`backend/pyinstaller.spec` is **not** ignored: `.gitignore` has `!backend/pyinstaller.spec` under the `*.spec` rule.

## Build triggers

- Push tag `v*` (e.g. `v0.1.1`) → workflow runs → ZIP on **Release** + **Artifacts**
- Or **Actions → Release Windows portable ZIP → Run workflow**

After fixing a failed build, move the tag to the commit that contains `backend/pyinstaller.spec` or push a new tag.
