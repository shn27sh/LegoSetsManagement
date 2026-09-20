"""Resolve install, data, web, and config paths for dev and portable Windows bundles."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_bundle_root() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return get_backend_root()


def get_backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def get_install_root() -> Path:
    explicit = os.environ.get("LCM_INSTALL_ROOT", "").strip()
    if explicit:
        return Path(explicit).resolve()
    if is_frozen():
        return Path(sys.executable).resolve().parent.parent
    return get_backend_root().parent


def get_data_dir() -> Path:
    explicit = os.environ.get("LCM_DATA_DIR", "").strip()
    if explicit:
        return Path(explicit).resolve()
    return get_install_root() / "data"


def get_web_root() -> Path | None:
    explicit = os.environ.get("LCM_WEB_ROOT", "").strip()
    if explicit:
        path = Path(explicit).resolve()
        return path if path.is_dir() else None
    candidate = get_install_root() / "web"
    return candidate if candidate.is_dir() else None


def get_config_env_path() -> Path:
    return get_install_root() / "config.env"


def get_alembic_ini_path() -> Path:
    explicit = os.environ.get("LCM_ALEMBIC_INI", "").strip()
    if explicit:
        return Path(explicit).resolve()
    if is_frozen():
        return get_bundle_root() / "alembic.ini"
    return get_backend_root() / "alembic.ini"


def get_alembic_script_location() -> Path:
    """Directory containing migration scripts (versions/, env.py)."""
    return get_alembic_ini_path().parent / "alembic"


def make_alembic_config():
    """Alembic config with script_location anchored to the ini file directory."""
    from alembic.config import Config

    config = Config(str(get_alembic_ini_path()))
    config.set_main_option("script_location", str(get_alembic_script_location()))
    return config


def sqlite_url_for_path(db_path: Path) -> str:
    return f"sqlite:///{db_path.resolve().as_posix()}"


def configure_runtime() -> Path:
    """Load portable config and set default paths. Returns install root."""
    install_root = get_install_root()
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    config_path = get_config_env_path()
    if config_path.is_file():
        load_dotenv(config_path, override=False)

    backend_env = get_backend_root() / ".env"
    if backend_env.is_file():
        load_dotenv(backend_env, override=False)

    portable_layout = bool(os.environ.get("LCM_INSTALL_ROOT", "").strip()) or is_frozen()
    db_url = sqlite_url_for_path(data_dir / "lego.db")
    log_path = str(data_dir / "server.log")
    failure_log_path = str(data_dir / "import_failures.log")
    failed_sets_csv_path = str(data_dir / "failedSets.csv")
    alembic_ini = str(get_alembic_ini_path())

    if portable_layout:
        os.environ["DATABASE_URL"] = db_url
        os.environ["LOG_FILE_PATH"] = log_path
        os.environ["IMPORT_FAILURE_LOG_PATH"] = failure_log_path
        os.environ["FAILED_SETS_CSV_PATH"] = failed_sets_csv_path
        os.environ["LCM_ALEMBIC_INI"] = alembic_ini
    else:
        os.environ.setdefault("DATABASE_URL", db_url)
        os.environ.setdefault("LOG_FILE_PATH", log_path)
        os.environ.setdefault("IMPORT_FAILURE_LOG_PATH", failure_log_path)
        os.environ.setdefault("FAILED_SETS_CSV_PATH", failed_sets_csv_path)
        os.environ.setdefault("LCM_ALEMBIC_INI", alembic_ini)

    web_root = get_web_root()
    if web_root is not None:
        os.environ.setdefault("LCM_WEB_ROOT", str(web_root))

    return install_root
