from dataclasses import replace
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.db.models import (
    CatalogMinifig,
    CatalogSet,
    ElementImage,
    PartColorElementId,
    MinifigPartInventoryLine,
    OwnedSetInventoryLine,
    Part,
    SetMinifigInventoryLine,
    SetPartInventoryLine,
    Theme,
)
from app.importers.rebrickable_sync_service import (
    RebrickableSyncResult,
    sync_catalog_for_set_nums,
    sync_one_catalog_set,
)
from app.rebrickable.dto import (
    CatalogSetDTO,
    ColorDTO,
    MinifigPartLineDTO,
    PartDTO,
    SetMinifigLineDTO,
    SetPartLineDTO,
    ThemeDTO,
)
from app.rebrickable.exceptions import RebrickableAPIError
from app.services.element_catalog import clear_element_catalog_cache
from app.services.image_download import DownloadedImage
from app.services.theme_catalog import clear_theme_catalog_cache
from tests.factories import (
    add_catalog_set,
    add_color,
    add_instance_line_for_set_part,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
    add_theme,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FakeRebrickableClient:
    def __init__(
        self,
        *,
        sets: dict[str, CatalogSetDTO] | None = None,
        themes: dict[int, ThemeDTO] | None = None,
        set_parts: dict[str, list[SetPartLineDTO]] | None = None,
        set_minifigs: dict[str, list[SetMinifigLineDTO]] | None = None,
        minifig_parts: dict[str, list[MinifigPartLineDTO]] | None = None,
        fail_set_nums: set[str] | None = None,
    ) -> None:
        self.sets = sets or {}
        self.themes = themes or {}
        self.set_parts = set_parts or {}
        self.set_minifigs = set_minifigs or {}
        self.minifig_parts = minifig_parts or {}
        self.fail_set_nums = fail_set_nums or set()

    def get_set(self, set_num: str) -> CatalogSetDTO:
        if set_num in self.fail_set_nums:
            raise RebrickableAPIError("not found", status_code=404)
        return self.sets[set_num]

    def get_theme(self, theme_id: int) -> ThemeDTO:
        return self.themes[theme_id]

    def iter_set_parts(self, set_num: str):
        yield from self.set_parts.get(set_num, [])

    def iter_set_minifigs(self, set_num: str):
        yield from self.set_minifigs.get(set_num, [])

    def iter_minifig_parts(self, minifig_num: str):
        yield from self.minifig_parts.get(minifig_num, [])


class FakeImageDownloader:
    def __init__(self) -> None:
        self.urls: list[str] = []

    def download(self, url: str) -> DownloadedImage:
        self.urls.append(url)
        return DownloadedImage(content=b"image-bytes", content_type="image/png")


def _sample_set() -> CatalogSetDTO:
    return CatalogSetDTO(
        set_num="6024-1",
        name="Police Car",
        year=1980,
        theme_external_id=67,
        num_parts=24,
        image_url="https://cdn.rebrickable.com/media/sets/6024-1.jpg",
        age=6,
    )


def _sample_part_line(
    part_num: str = "3024",
    *,
    is_spare: bool = False,
    image_url: str | None = None,
) -> SetPartLineDTO:
    return SetPartLineDTO(
        part=PartDTO(part_num=part_num, name="Plate", image_url=image_url, aliases=()),
        color=ColorDTO(external_id=0, name="Black", rgb="05131D"),
        quantity=4,
        is_spare=is_spare,
        is_alternate=False,
        image_url=image_url,
        inventory_id=100,
    )


@pytest.fixture
def fake_client() -> FakeRebrickableClient:
    return FakeRebrickableClient(
        sets={"6024-1": _sample_set()},
        themes={67: ThemeDTO(external_id=67, name="Town")},
        set_parts={"6024-1": [_sample_part_line("3024"), _sample_part_line("3005", is_spare=True)]},
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
        minifig_parts={
            "cop01": [
                MinifigPartLineDTO(
                    part=PartDTO(
                        part_num="973",
                        name="Torso",
                        image_url=None,
                    ),
                    color=ColorDTO(external_id=0, name="Black", rgb=None),
                    quantity=1,
                    is_spare=False,
                    image_url="https://cdn.example/973-element.png",
                )
            ]
        },
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


def test_sync_two_phase_progress_labels(db_session, fake_client, elements_csv) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    db_session.commit()
    labels: list[str] = []

    def on_progress(_current: int, _total: int, label: str) -> None:
        labels.append(label)

    downloader = FakeImageDownloader()
    sync_catalog_for_set_nums(
        db_session,
        fake_client,
        ["6024-1"],
        download_set_images=True,
        image_downloader=downloader,
        on_progress=on_progress,
    )

    assert any("Syncing catalog" in label for label in labels)
    assert any("Downloading images" in label for label in labels)


def test_sync_populates_catalog(db_session, fake_client, elements_csv) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    db_session.commit()

    result = sync_catalog_for_set_nums(db_session, fake_client, ["6024-1"])
    db_session.commit()

    assert result.sets_synced == 1
    assert result.sets_failed == []
    assert result.parts_upserted >= 2
    assert result.inventory_lines_written >= 3

    updated = db_session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == 6024,
            CatalogSet.set_variant == 1,
        )
    )
    assert updated is not None
    assert updated.name == "Police Car"
    assert updated.source == "rebrickable"
    assert db_session.scalar(select(func.count()).select_from(SetPartInventoryLine)) == 1
    assert db_session.scalar(select(func.count()).select_from(SetMinifigInventoryLine)) == 1
    assert db_session.scalar(select(func.count()).select_from(CatalogMinifig)) == 1
    assert db_session.scalars(
        select(PartColorElementId.element_id).order_by(PartColorElementId.element_id)
    ).all() == ["302400", "6252045", "973000"]
    clear_element_catalog_cache()


def test_sync_uses_parent_theme_from_csv(db_session, tmp_path, monkeypatch) -> None:
    themes_csv = tmp_path / "themes.csv"
    themes_csv.write_text(
        "id,name,parent_id\n"
        "52,City,\n"
        "57,Farm,52\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("THEMES_CSV_PATH", str(themes_csv))
    clear_theme_catalog_cache()
    catalog = add_catalog_set(db_session, set_number=60181)
    add_owned_set(db_session, catalog)
    db_session.commit()
    client = FakeRebrickableClient(
        sets={
            "60181-1": CatalogSetDTO(
                set_num="60181-1",
                name="Forest Tractor",
                year=2018,
                theme_external_id=57,
                num_parts=174,
                image_url=None,
            )
        },
        set_parts={"60181-1": []},
    )

    sync_one_catalog_set(db_session, client, "60181-1")
    db_session.commit()

    theme = db_session.scalar(select(Theme).where(Theme.external_id == 52))
    assert theme is not None
    assert theme.name == "City"
    updated = db_session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == 60181,
            CatalogSet.set_variant == 1,
        )
    )
    assert updated is not None
    assert updated.theme_id == theme.id
    clear_theme_catalog_cache()


def test_second_sync_replaces_inventory(db_session, fake_client) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    db_session.commit()

    sync_catalog_for_set_nums(db_session, fake_client, ["6024-1"])
    db_session.commit()

    fake_client.set_parts["6024-1"] = [_sample_part_line("9999")]
    sync_catalog_for_set_nums(db_session, fake_client, ["6024-1"])
    db_session.commit()

    lines = db_session.scalars(select(SetPartInventoryLine)).all()
    assert len(lines) == 1
    part = db_session.scalar(select(Part).where(Part.part_num == "9999"))
    assert part is not None


def test_sync_preserves_local_fields_and_missing_counts(db_session) -> None:
    old_theme = add_theme(db_session, external_id=500, name="Local Theme")
    catalog = add_catalog_set(db_session, theme=old_theme)
    catalog.name = "Local Name"
    catalog.year = 1977
    catalog.num_parts = 12
    catalog.image_url = "https://cdn.example/old-set.jpg"
    part = add_part(db_session, part_num="3024")
    color = add_color(db_session, external_id=0, name="Black")
    catalog_line = add_set_part_inventory_line(
        db_session,
        catalog_set=catalog,
        part=part,
        color=color,
        quantity=4,
    )
    owned = add_owned_set(db_session, catalog, investigated=True, label="My copy")
    owned.age = 9
    owned.notes = "Keep this note"
    instance_line = add_instance_line_for_set_part(
        db_session,
        owned_set=owned,
        catalog_line=catalog_line,
        quantity=4,
        quantity_missing=2,
    )
    db_session.commit()
    updated_line = replace(_sample_part_line("3024"), quantity=7)
    client = FakeRebrickableClient(
        sets={
            "6024-1": CatalogSetDTO(
                set_num="6024-1",
                name="Remote Name",
                year=2024,
                theme_external_id=67,
                num_parts=99,
                image_url="https://cdn.example/new-set.jpg",
                age=6,
            )
        },
        themes={67: ThemeDTO(external_id=67, name="Remote Theme")},
        set_parts={"6024-1": [updated_line]},
    )

    result = sync_catalog_for_set_nums(db_session, client, ["6024-1"])
    db_session.commit()

    assert result.sets_synced == 1
    db_session.refresh(catalog)
    db_session.refresh(owned)
    db_session.refresh(instance_line)
    assert catalog.name == "Remote Name"
    assert catalog.num_parts == 99
    assert catalog.image_url == "https://cdn.example/new-set.jpg"
    assert catalog.year == 1977
    assert catalog.theme_id == old_theme.id
    assert owned.age == 9
    assert owned.investigated is True
    assert owned.label == "My copy"
    assert owned.notes == "Keep this note"
    assert instance_line.quantity == 7
    assert instance_line.quantity_missing == 2


def test_sync_records_failure_without_corrupting_other_set(db_session, fake_client) -> None:
    catalog_ok = add_catalog_set(db_session)
    catalog_bad = add_catalog_set(db_session, set_number=77777)
    add_owned_set(db_session, catalog_ok)
    add_owned_set(db_session, catalog_bad)
    db_session.commit()

    fake_client.sets["77777-1"] = CatalogSetDTO(
        set_num="77777-1",
        name=None,
        year=None,
        theme_external_id=None,
        num_parts=None,
        image_url=None,
    )
    fake_client.fail_set_nums.add("77777-1")

    result = sync_catalog_for_set_nums(
        db_session, fake_client, ["6024-1", "77777-1"]
    )
    db_session.commit()

    assert result.sets_synced == 1
    assert len(result.sets_failed) == 1
    assert result.sets_failed[0].set_num == "77777-1"
    assert "404" in result.sets_failed[0].message

    ok_set = db_session.scalar(
        select(CatalogSet).where(
            CatalogSet.set_number == 6024,
            CatalogSet.set_variant == 1,
        )
    )
    assert ok_set is not None
    assert ok_set.name == "Police Car"


def test_sync_can_download_set_images(db_session, fake_client) -> None:
    catalog = add_catalog_set(db_session)
    catalog.image_blob = b"dummy-set-image"
    catalog.image_content_type = "image/png"
    catalog.image_byte_size = len(catalog.image_blob)
    add_owned_set(db_session, catalog)
    db_session.commit()
    downloader = FakeImageDownloader()

    result = sync_catalog_for_set_nums(
        db_session,
        fake_client,
        ["6024-1"],
        download_set_images=True,
        image_downloader=downloader,
    )
    db_session.commit()

    assert result.set_images_downloaded == 1
    assert result.minifig_images_downloaded == 1
    assert result.image_downloads_failed == []
    assert downloader.urls == [
        "https://cdn.rebrickable.com/media/sets/6024-1.jpg",
        "https://cdn.example/cop01.png",
    ]
    db_session.expire_all()
    updated = db_session.get(CatalogSet, catalog.id)
    assert updated is not None
    assert updated.image_blob == b"image-bytes"
    assert updated.image_content_type == "image/png"
    minifig = db_session.scalar(select(CatalogMinifig).where(CatalogMinifig.minifig_num == "cop01"))
    assert minifig is not None
    assert minifig.image_blob == b"image-bytes"
    assert minifig.image_content_type == "image/png"


def test_sync_downloads_only_missing_part_images(
    db_session, fake_client, elements_csv
) -> None:
    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog)
    fake_client.set_parts["6024-1"] = [
        _sample_part_line("3024", image_url="https://cdn.example/3024.png"),
        _sample_part_line("3001", image_url="https://cdn.example/3001.png"),
    ]
    db_session.commit()
    sync_catalog_for_set_nums(db_session, fake_client, ["6024-1"])
    line = db_session.scalar(
        select(SetPartInventoryLine)
        .join(Part, SetPartInventoryLine.part_id == Part.id)
        .where(Part.part_num == "3024")
    )
    assert line is not None
    add_instance_line_for_set_part(
        db_session,
        owned_set=owned,
        catalog_line=line,
        quantity_missing=1,
    )
    db_session.commit()
    downloader = FakeImageDownloader()

    result = sync_catalog_for_set_nums(
        db_session,
        fake_client,
        ["6024-1"],
        download_missing_part_images=True,
        image_downloader=downloader,
    )
    db_session.commit()

    assert result.part_images_downloaded == 1
    assert downloader.urls == ["https://cdn.example/3024.png"]
    element_row = db_session.scalar(
        select(ElementImage).where(ElementImage.element_id == "302400")
    )
    other_element = db_session.scalar(
        select(ElementImage).where(ElementImage.element_id == "300100")
    )
    assert element_row is not None
    assert element_row.image_blob == b"image-bytes"
    assert other_element is None or other_element.image_blob is None


def test_sync_downloads_missing_minifig_part_images(
    db_session, fake_client, elements_csv
) -> None:
    catalog = add_catalog_set(db_session)
    owned = add_owned_set(db_session, catalog)
    db_session.commit()
    sync_catalog_for_set_nums(db_session, fake_client, ["6024-1"])
    minifig_line = db_session.scalar(
        select(MinifigPartInventoryLine)
        .join(Part, MinifigPartInventoryLine.part_id == Part.id)
        .where(Part.part_num == "973")
    )
    assert minifig_line is not None
    instance_line = db_session.scalar(
        select(OwnedSetInventoryLine).where(
            OwnedSetInventoryLine.owned_set_id == owned.id,
            OwnedSetInventoryLine.minifig_part_inventory_line_id == minifig_line.id,
        )
    )
    assert instance_line is not None
    instance_line.quantity_missing = 1
    db_session.commit()
    downloader = FakeImageDownloader()

    result = sync_catalog_for_set_nums(
        db_session,
        fake_client,
        ["6024-1"],
        download_missing_part_images=True,
        image_downloader=downloader,
    )
    db_session.commit()

    assert result.part_images_downloaded == 1
    assert downloader.urls == ["https://cdn.example/973-element.png"]
    element_row = db_session.scalar(
        select(ElementImage).where(ElementImage.element_id == "973000")
    )
    assert element_row is not None
    assert element_row.image_blob == b"image-bytes"


def test_sync_downloads_all_part_images(db_session, fake_client, elements_csv) -> None:
    catalog = add_catalog_set(db_session)
    add_owned_set(db_session, catalog)
    fake_client.set_parts["6024-1"] = [
        _sample_part_line("3024", image_url="https://cdn.example/3024.png"),
        _sample_part_line("3001", image_url="https://cdn.example/3001.png"),
    ]
    db_session.commit()
    sync_catalog_for_set_nums(db_session, fake_client, ["6024-1"])
    db_session.commit()
    stale_part = db_session.scalar(select(Part).where(Part.part_num == "3024"))
    assert stale_part is not None
    stale_part.image_blob = b"dummy-part-image"
    stale_part.image_content_type = "image/png"
    stale_part.image_byte_size = len(stale_part.image_blob)
    db_session.commit()
    downloader = FakeImageDownloader()

    result = sync_catalog_for_set_nums(
        db_session,
        fake_client,
        ["6024-1"],
        download_all_part_images=True,
        image_downloader=downloader,
    )
    db_session.commit()

    assert result.part_images_downloaded == 3
    assert downloader.urls == [
        "https://cdn.example/3024.png",
        "https://cdn.example/3001.png",
        "https://cdn.example/973-element.png",
    ]
    element_rows = db_session.scalars(
        select(ElementImage).where(
            ElementImage.element_id.in_(["302400", "300100", "973000"])
        )
    ).all()
    assert len(element_rows) == 3
    assert all(row.image_blob == b"image-bytes" for row in element_rows)
