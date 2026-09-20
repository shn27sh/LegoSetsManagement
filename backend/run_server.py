#!/usr/bin/env python3
"""Production / portable entrypoint: configure paths, migrate DB, serve API + UI."""

from __future__ import annotations

import os
import threading
import time
import webbrowser

from app.db.migration_ops import upgrade_database_to_head
from app.runtime_paths import configure_runtime


def main() -> None:
    configure_runtime()
    upgrade_database_to_head()

    host = os.environ.get("LCM_HOST", "127.0.0.1")
    port = int(os.environ.get("LCM_PORT", "8000"))
    open_browser = os.environ.get("LCM_OPEN_BROWSER", "1").lower() not in (
        "0",
        "false",
        "no",
    )
    url = f"http://{host}:{port}/"

    if open_browser:

        def _open() -> None:
            time.sleep(1.5)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        log_level=os.environ.get("LOG_LEVEL", "warning").lower(),
    )


if __name__ == "__main__":
    main()
