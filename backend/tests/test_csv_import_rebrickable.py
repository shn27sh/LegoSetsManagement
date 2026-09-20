"""CSV import with Rebrickable catalog fetch (Phase 12)."""

import pytest
from sqlalchemy import func, select

from app.db.models import CatalogSet, OwnedSet, Part, SetPartInventoryLine
from app.importers.csv_import_service import import_set_list
from app.rebrickable.dto import CatalogSetDTO, SetMinifigLineDTO, ThemeDTO
from app.services.element_catalog import clear_element_catalog_cache
from tests.test_rebrickable_sync_service import (
    FakeImageDownloader,
    FakeRebrickableClient,
    _sample_part_line,
    _sample_set,
)


@pytest.fixture
def elements_csv(tmp_path, monkeypatch):
    path = tmp_path / "elements.csv"
    path.write_text(
        "element_id,part_num,color_id,design_id\n"
        "302400,3024,0,3024\n"
        "6252045,3024,0,3024\n"
        "300100,3001,0,3001\n"
        "973000,973,0,973\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ELEMENTS_CSV_PATH", str(path))
    clear_element_catalog_cache()


def _client_for_6024() -> FakeRebrickableClient:
    return FakeRebrickableClient(
        sets={"6024-1": _sample_set()},
        themes={67: ThemeDTO(external_id=67, name="Town")},
        set_parts={"6024-1": [_sample_part_line()]},
    )


def test_csv_import_fetches_catalog_and_inventory(db_session) -> None:
    result = import_set_list(
        db_session, "6024-1", client=_client_for_6024()
    )
    db_session.commit()

    assert result.instances_created == 1
    assert result.sets_fetched == 1
    assert result.catalog_stubs_created == 0
    assert result.sets_failed == []
    catalog = db_session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == 6024,
            CatalogSet.set_variant == 1,
        )
    )
    assert catalog is not None
    assert catalog.source == "rebrickable"
    assert catalog.name == "Police Car"
    assert db_session.scalar(select(func.count()).select_from(SetPartInventoryLine)) == 1
    assert db_session.scalar(select(func.count()).select_from(OwnedSet)) == 1


def test_csv_import_stores_image_urls(db_session) -> None:
    import_set_list(db_session, "6024-1", client=_client_for_6024())
    db_session.commit()

    catalog = db_session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == 6024,
            CatalogSet.set_variant == 1,
        )
    )
    part = db_session.scalar(select(Part).where(Part.part_num == "3024"))
    assert catalog is not None
    assert catalog.image_url == "https://cdn.rebrickable.com/media/sets/6024-1.jpg"
    assert part is not None
    assert part.image_url is None


def test_csv_import_downloads_images(db_session, elements_csv) -> None:
    from app.db.models import CatalogMinifig, ElementImage

    client = FakeRebrickableClient(
        sets={"6024-1": _sample_set()},
        themes={67: ThemeDTO(external_id=67, name="Town")},
        set_parts={
            "6024-1": [
                _sample_part_line(
                    "3024",
                    image_url="https://cdn.example/3024.png",
                )
            ]
        },
        set_minifigs={
            "6024-1": [
                SetMinifigLineDTO(
                    minifig_num="cop01",
                    name="Police Officer",
                    image_url="https://cdn.example/cop01.png",
                    quantity=1,
                )
            ]
        },
    )
    downloader = FakeImageDownloader()
    result = import_set_list(
        db_session,
        "6024-1",
        client=client,
        image_downloader=downloader,
    )
    db_session.commit()

    assert result.set_images_downloaded == 1
    assert result.minifig_images_downloaded == 1
    assert result.part_images_downloaded == 1
    assert result.image_downloads_failed == []
    assert downloader.urls == [
        "https://cdn.rebrickable.com/media/sets/6024-1.jpg",
        "https://cdn.example/cop01.png",
        "https://cdn.example/3024.png",
    ]
    catalog = db_session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == 6024,
            CatalogSet.set_variant == 1,
        )
    )
    assert catalog is not None
    assert catalog.image_blob == b"image-bytes"
    minifig = db_session.scalar(
        select(CatalogMinifig).where(CatalogMinifig.minifig_num == "cop01")
    )
    assert minifig is not None
    assert minifig.image_blob == b"image-bytes"
    element_row = db_session.scalar(
        select(ElementImage).where(ElementImage.element_id == "302400")
    )
    assert element_row is not None
    assert element_row.image_blob == b"image-bytes"


def test_csv_import_reports_rebrickable_failure_but_creates_stub(db_session) -> None:
    client = FakeRebrickableClient(
        sets={"6024-1": _sample_set()},
        fail_set_nums={"6024-1"},
    )
    result = import_set_list(db_session, "6024-1", client=client)
    db_session.commit()

    assert result.instances_created == 1
    assert result.sets_fetched == 0
    assert result.catalog_stubs_created == 1
    assert len(result.sets_failed) == 1
    assert result.sets_failed[0].set_num == 6024
    catalog = db_session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == 6024,
            CatalogSet.set_variant == 1,
        )
    )
    assert catalog is not None
    assert catalog.source == "csv_import"


def test_csv_import_failure_preserves_previous_successes(db_session) -> None:
    client = FakeRebrickableClient(
        sets={
            "6024-1": _sample_set(),
            "10281-1": CatalogSetDTO(
                set_num="10281-1",
                name="Bonsai",
                year=2021,
                theme_external_id=67,
                num_parts=100,
                image_url=None,
            ),
            "9999-1": CatalogSetDTO(
                set_num="9999-1",
                name="Will Fail",
                year=1999,
                theme_external_id=67,
                num_parts=1,
                image_url=None,
            ),
        },
        themes={67: ThemeDTO(external_id=67, name="Town")},
        set_parts={
            "6024-1": [_sample_part_line()],
            "10281-1": [_sample_part_line("3001")],
        },
        fail_set_nums={"9999-1"},
    )

    result = import_set_list(db_session, "6024-1,9999-1,10281-1", client=client)
    db_session.commit()

    assert result.instances_created == 3
    assert result.sets_fetched == 2
    assert result.catalog_stubs_created == 1
    assert len(result.sets_failed) == 1
    assert db_session.scalar(select(func.count()).select_from(OwnedSet)) == 3
    set_numbers = db_session.scalars(
        select(CatalogSet.set_number).order_by(CatalogSet.set_number)
    ).all()
    assert set_numbers == [6024, 9999, 10281]


def test_csv_import_second_token_creates_second_instance(db_session) -> None:
    client = _client_for_6024()
    import_set_list(db_session, "6024-1", client=client)
    db_session.commit()
    result = import_set_list(db_session, "6024-1", client=client, existing_set_mode="copy")
    db_session.commit()

    assert result.instances_created == 1
    assert result.sets_fetched == 0
    assert db_session.scalar(select(func.count()).select_from(OwnedSet)) == 2


def test_csv_import_sets_age_on_new_instance(db_session) -> None:
    result = import_set_list(
        db_session, "6024-1", client=_client_for_6024()
    )
    db_session.commit()

    assert result.sets_fetched == 1
    owned = db_session.scalar(select(OwnedSet))
    assert owned is not None
    assert owned.age == 6


def test_csv_import_second_instance_gets_age(db_session) -> None:
    client = _client_for_6024()
    import_set_list(db_session, "6024-1", client=client)
    db_session.commit()

    result = import_set_list(db_session, "6024-1", client=client, existing_set_mode="copy")
    db_session.commit()

    assert result.instances_created == 1
    ages = db_session.scalars(select(OwnedSet.age).order_by(OwnedSet.id)).all()
    assert ages == [6, 6]


def test_csv_import_two_set_nums_in_one_file(db_session) -> None:
    client = FakeRebrickableClient(
        sets={
            "6024-1": _sample_set(),
            "10281-1": CatalogSetDTO(
                set_num="10281-1",
                name="Bonsai",
                year=2021,
                theme_external_id=67,
                num_parts=100,
                image_url=None,
            ),
        },
        themes={67: ThemeDTO(external_id=67, name="Town")},
        set_parts={
            "6024-1": [_sample_part_line()],
            "10281-1": [_sample_part_line("3001")],
        },
    )
    result = import_set_list(db_session, "6024-1,10281-1", client=client)
    db_session.commit()

    assert result.instances_created == 2
    assert result.sets_fetched == 2
    assert db_session.scalar(select(func.count()).select_from(CatalogSet)) == 2
