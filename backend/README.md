# Backend (this folder)

Python package layout: `app/` (FastAPI), `alembic/` (migrations), `tests/`.

## Install

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

If editable install is unavailable, use the flat lock-style file:

```bash
pip install -r requirements-dev.txt
```

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Migrations

```bash
mkdir -p data
alembic upgrade head
```
