from pathlib import Path

from alembic.script import ScriptDirectory

from app.runtime_paths import (
    configure_runtime,
    get_alembic_script_location,
    get_data_dir,
    get_install_root,
    make_alembic_config,
    sqlite_url_for_path,
)


def test_configure_runtime_uses_install_root_data(tmp_path, monkeypatch) -> None:
    install = tmp_path / "app"
    data = install / "data"
    install.mkdir()
    monkeypatch.setenv("LCM_INSTALL_ROOT", str(install))
    monkeypatch.delenv("DATABASE_URL", raising=False)

    configure_runtime()

    assert get_install_root() == install.resolve()
    assert get_data_dir() == data.resolve()
    assert data.is_dir()
    assert Path(get_data_dir(), "lego.db").as_posix() in __import__(
        "os"
    ).environ["DATABASE_URL"]


def test_sqlite_url_for_path_windows_friendly(tmp_path) -> None:
    db = tmp_path / "lego.db"
    url = sqlite_url_for_path(db)
    assert url.startswith("sqlite:///")
    assert "lego.db" in url


def test_make_alembic_config_script_location_not_cwd_relative(
    tmp_path: Path, monkeypatch
) -> None:
    """Portable launcher cwd differs from the bundle dir containing alembic.ini."""
    bundle = tmp_path / "bundle"
    launcher_cwd = tmp_path / "launcher"
    bundle.mkdir()
    launcher_cwd.mkdir()

    alembic_dir = bundle / "alembic"
    versions = alembic_dir / "versions"
    versions.mkdir(parents=True)
    (alembic_dir / "env.py").write_text("# stub\n")
    (versions / "0001_stub.py").write_text(
        'revision = "0001"\ndown_revision = None\n'
    )
    (bundle / "alembic.ini").write_text(
        "[alembic]\nscript_location = %(here)s/alembic\n"
    )

    monkeypatch.chdir(launcher_cwd)
    monkeypatch.setenv("LCM_ALEMBIC_INI", str(bundle / "alembic.ini"))

    config = make_alembic_config()
    script = ScriptDirectory.from_config(config)

    assert get_alembic_script_location() == alembic_dir.resolve()
    assert script.dir == str(alembic_dir.resolve())
    assert script.get_current_head() == "0001"
