"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.routes import images, imports, media, owned_sets, parts, reports, search
from app.db.migration_check import ensure_database_at_head
from app.frontend_static import register_frontend_routes
from app.logging_config import configure_logging

load_dotenv()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    ensure_database_at_head()
    yield


app = FastAPI(
    title="LEGO Collection Manager API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(imports.router, prefix="/api")
app.include_router(owned_sets.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(images.router, prefix="/api")
app.include_router(parts.router, prefix="/api")
app.include_router(reports.router, prefix="/api")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


register_frontend_routes(app)
