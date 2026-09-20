from unittest.mock import patch

import pytest

from app.importers.rebrickable_sync_service import (
    ImageSyncFailure,
    RebrickableSyncResult,
    SetSyncFailure,
)
from tests.factories import add_catalog_set, add_owned_set


def test_post_sync_requires_api_key(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REBRICKABLE_API_KEY", raising=False)
    response = api_client.post("/api/imports/rebrickable/sync", json={})
    assert response.status_code == 400
    assert "REBRICKABLE_API_KEY" in response.json()["detail"]


def test_post_sync_success(api_client, db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog)
    db_session.commit()

    mock_result = RebrickableSyncResult(
        sets_synced=1,
        sets_failed=[],
        parts_upserted=3,
        inventory_lines_written=5,
    )

    with patch(
        "app.api.routes.imports.sync_rebrickable",
        return_value=mock_result,
    ) as mock_sync:
        response = api_client.post(
            "/api/imports/rebrickable/sync",
            json={"owned_set_ids": [owned.id]},
        )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "sets_synced": 1,
        "sets_failed": [],
        "parts_upserted": 3,
        "inventory_lines_written": 5,
        "set_images_downloaded": 0,
        "minifig_images_downloaded": 0,
        "part_images_downloaded": 0,
        "image_downloads_failed": [],
    }
    mock_sync.assert_called_once()
    assert mock_sync.call_args.kwargs["owned_set_ids"] == [owned.id]
    assert mock_sync.call_args.kwargs["download_set_images"] is False
    assert mock_sync.call_args.kwargs["download_missing_part_images"] is False


def test_post_sync_empty_body_syncs_all(
    api_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    mock_result = RebrickableSyncResult()

    with patch(
        "app.api.routes.imports.sync_rebrickable",
        return_value=mock_result,
    ) as mock_sync:
        response = api_client.post("/api/imports/rebrickable/sync")

    assert response.status_code == 200
    mock_sync.assert_called_once()
    assert mock_sync.call_args.kwargs["owned_set_ids"] is None


def test_post_sync_returns_failures(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    mock_result = RebrickableSyncResult(
        sets_synced=0,
        sets_failed=[SetSyncFailure(set_num="bad-1", message="HTTP 404 from Rebrickable")],
        parts_upserted=0,
        inventory_lines_written=0,
    )

    with patch(
        "app.api.routes.imports.sync_rebrickable",
        return_value=mock_result,
    ):
        response = api_client.post("/api/imports/rebrickable/sync", json={})

    assert response.status_code == 200
    body = response.json()
    assert body["sets_failed"] == [
        {"set_num": "bad-1", "message": "HTTP 404 from Rebrickable"}
    ]


def test_post_sync_passes_image_options(api_client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    mock_result = RebrickableSyncResult(
        set_images_downloaded=1,
        part_images_downloaded=2,
        image_downloads_failed=[
            ImageSyncFailure(
                target="part:1",
                url="https://cdn.example/part.png",
                message="HTTP 404",
            )
        ],
    )

    with patch(
        "app.api.routes.imports.sync_rebrickable",
        return_value=mock_result,
    ) as mock_sync:
        response = api_client.post(
            "/api/imports/rebrickable/sync",
            json={
                "owned_set_ids": [10],
                "download_set_images": True,
                "part_image_download_mode": "missing",
            },
        )

    assert response.status_code == 200
    assert mock_sync.call_args.kwargs["owned_set_ids"] == [10]
    assert mock_sync.call_args.kwargs["download_set_images"] is True
    assert mock_sync.call_args.kwargs["download_missing_part_images"] is True
    assert mock_sync.call_args.kwargs["download_all_part_images"] is False
    body = response.json()
    assert body["set_images_downloaded"] == 1
    assert body["part_images_downloaded"] == 2
    assert body["image_downloads_failed"] == [
        {
            "target": "part:1",
            "url": "https://cdn.example/part.png",
            "message": "HTTP 404",
        }
    ]


def test_post_sync_passes_all_part_image_mode(
    api_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")
    mock_result = RebrickableSyncResult(part_images_downloaded=3)

    with patch(
        "app.api.routes.imports.sync_rebrickable",
        return_value=mock_result,
    ) as mock_sync:
        response = api_client.post(
            "/api/imports/rebrickable/sync",
            json={"part_image_download_mode": "all"},
        )

    assert response.status_code == 200
    assert mock_sync.call_args.kwargs["download_missing_part_images"] is False
    assert mock_sync.call_args.kwargs["download_all_part_images"] is True
    assert response.json()["part_images_downloaded"] == 3


def test_post_sync_rejects_invalid_part_image_mode(
    api_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REBRICKABLE_API_KEY", "test-key")

    response = api_client.post(
        "/api/imports/rebrickable/sync",
        json={"part_image_download_mode": "everything"},
    )

    assert response.status_code == 422
    assert "part_image_download_mode" in response.text
