"""Database engine (sessions added when routes use the ORM)."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.sqlite_pragmas import configure_sqlite_engine

DEFAULT_DATABASE_URL = "sqlite:///./data/lego.db"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_engine():
    url = get_database_url()
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {
            "check_same_thread": False,
            "timeout": 30,
        }
    engine = create_engine(url, **kwargs)
    configure_sqlite_engine(engine)
    return engine


def get_session_factory():
    return sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
