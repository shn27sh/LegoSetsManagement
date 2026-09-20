from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


def test_serves_built_frontend_when_web_root_set(
    tmp_path: Path, monkeypatch
) -> None:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html><body>Hello LCM</body></html>", encoding="utf-8")
    assets = web / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('ok');", encoding="utf-8")

    monkeypatch.setenv("LCM_WEB_ROOT", str(web))
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Hello LCM" in response.text
    assert response.headers.get("cache-control") == "no-cache"

    asset_response = client.get("/assets/app.js")
    assert asset_response.status_code == 200
    assert asset_response.headers.get("cache-control") == "public, max-age=31536000, immutable"

    spa_response = client.get("/settings")
    assert spa_response.status_code == 200
    assert "Hello LCM" in spa_response.text
    assert spa_response.headers.get("cache-control") == "no-cache"
