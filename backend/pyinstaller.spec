# PyInstaller spec for the portable Windows server bundle (one-folder layout).
# Run from backend/: pyinstaller pyinstaller.spec

from pathlib import Path

backend = Path(SPECPATH)

alembic_ini = backend / "alembic.ini"
alembic_dir = backend / "alembic"

datas = [
    (str(alembic_ini), "."),
    (str(alembic_dir), "alembic"),
]

hiddenimports = [
    "alembic",
    "alembic.runtime.migration",
    "alembic.script",
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.importer",
    "click",
    "httptools",
    "websockets",
    "watchfiles",
    "sqlalchemy.sql.default_comparator",
    "multipart",
    "python_multipart",
    "app",
    "app.main",
    "app.api.routes.imports",
    "app.api.routes.owned_sets",
    "app.api.routes.search",
    "app.api.routes.media",
    "app.api.routes.images",
    "app.api.routes.parts",
    "app.api.routes.reports",
]

a = Analysis(
    [str(backend / "run_server.py")],
    pathex=[str(backend)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="lcm-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name="lcm-server",
)
