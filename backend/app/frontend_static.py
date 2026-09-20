"""Serve the production Vite build when LCM_WEB_ROOT is configured."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.runtime_paths import get_web_root

_INDEX_CACHE_CONTROL = {"Cache-Control": "no-cache"}
_ASSET_CACHE_CONTROL = {"Cache-Control": "public, max-age=31536000, immutable"}


def register_frontend_routes(app: FastAPI) -> None:
    @app.get("/", include_in_schema=False)
    async def serve_index() -> FileResponse:
        web_root = get_web_root()
        if web_root is None:
            raise HTTPException(status_code=404, detail="Not Found")
        index_html = web_root / "index.html"
        if not index_html.is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index_html, headers=_INDEX_CACHE_CONTROL)

    @app.get("/assets/{asset_path:path}", include_in_schema=False)
    async def serve_asset(asset_path: str) -> FileResponse:
        web_root = get_web_root()
        if web_root is None:
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = web_root / "assets" / asset_path
        if not candidate.is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(candidate, headers=_ASSET_CACHE_CONTROL)

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def serve_spa(spa_path: str) -> FileResponse:
        if spa_path.startswith("api/") or spa_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        web_root = get_web_root()
        if web_root is None:
            raise HTTPException(status_code=404, detail="Not Found")
        index_html = web_root / "index.html"
        candidate = web_root / spa_path
        if candidate.is_file():
            return FileResponse(candidate)
        if index_html.is_file():
            return FileResponse(index_html, headers=_INDEX_CACHE_CONTROL)
        raise HTTPException(status_code=404, detail="Not Found")
