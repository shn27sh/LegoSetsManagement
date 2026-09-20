"""Tests for database import service."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import models as _models  # noqa: F401
from app.db.base import Base
from app.db.models import CatalogSet, Color, OwnedSet, OwnedSetInventoryLine, Part, Theme
from app.importers.database_import_service import import_from_database_session
from tests.factories import (
    TINY_PNG,
    add_catalog_set,
    add_color,
    add_missing_item_for_set_line,
    add_owned_set,
    add_part,
    add_set_part_inventory_line,
    add_theme,
    utc_now,
)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def _populate_source_set(
    session: Session,
    *,
    set_number: int = 6024,
    set_variant: int = 1,
    name: str = "Police Car",
    theme_name: str = "Town",
    age: int | None = 6,
    label: str | None = "My copy",
    quantity_missing: int = 0,
    theme: Theme | None = None,
) -> tuple[CatalogSet, OwnedSet]:
    if theme is None:
        theme = session.scalar(select(Theme).where(Theme.external_id == 67))
    if theme is None:
        theme = add_theme(session, external_id=67, name=theme_name)
    catalog = add_catalog_set(session, set_number=set_number, set_variant=set_variant, theme=theme)
    catalog.name = name
    catalog.image_blob = TINY_PNG
    catalog.image_content_type = "image/png"
    catalog.image_byte_size = len(TINY_PNG)
    part = session.scalar(select(Part).where(Part.part_num == "3024"))
    if part is None:
        part = add_part(session, part_num="3024")
    part.name = "Plate 1 x 1"
    part.image_blob = TINY_PNG
    color = session.scalar(select(Color).where(Color.external_id == 0))
    if color is None:
        color = add_color(session, external_id=0, name="Black")
    line = add_set_part_inventory_line(
        session, catalog_set=catalog, part=part, color=color, quantity=4
    )
    owned = add_owned_set(session, catalog, label=label, with_inventory=False)
    owned.age = age
    instance = OwnedSetInventoryLine(
        owned_set_id=owned.id,
        set_part_inventory_line_id=line.id,
        minifig_part_inventory_line_id=None,
        quantity=4,
        quantity_missing=quantity_missing,
    )
    session.add(instance)
    session.flush()
    if quantity_missing > 0:
        from app.db.models import MissingItem

        session.add(
            MissingItem(
                owned_set_id=owned.id,
                owned_set_inventory_line_id=instance.id,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
    session.flush()
    return catalog, owned


def test_add_only_new_imports_missing_sets() -> None:
    source = _make_session()
    target = _make_session()
    _populate_source_set(source, set_number=6024)
    _populate_source_set(source, set_number=9999, name="New Set")
    source.commit()

    result = import_from_database_session(target, source, mode="add_only_new")
    target.commit()

    assert result.sets_added == 2
    assert result.sets_skipped == 0
    assert result.instances_created == 2
    assert target.scalar(select(CatalogSet).where(CatalogSet.set_number == 9999)) is not None


def test_add_only_new_skips_existing_sets() -> None:
    source = _make_session()
    target = _make_session()
    _populate_source_set(source, set_number=6024, name="Source Name")
    _populate_source_set(target, set_number=6024, name="Target Name")
    source.commit()
    target.commit()

    result = import_from_database_session(target, source, mode="add_only_new")
    target.commit()

    assert result.sets_added == 0
    assert result.sets_skipped == 1
    assert result.skipped_set_nums == ["6024-1"]
    catalog = target.scalar(select(CatalogSet).where(CatalogSet.set_number == 6024))
    assert catalog is not None
    assert catalog.name == "Target Name"


def test_add_and_update_refreshes_catalog_without_overwriting_theme() -> None:
    source = _make_session()
    target = _make_session()
    source_theme = add_theme(source, external_id=67, name="Source Theme")
    target_theme = add_theme(target, external_id=99, name="Target Theme")
    source_catalog = add_catalog_set(
        source, set_number=6024, set_variant=1, theme=source_theme
    )
    source_catalog.name = "Updated Name"
    source_catalog.image_blob = TINY_PNG
    target_catalog = add_catalog_set(
        target, set_number=6024, set_variant=1, theme=target_theme
    )
    target_catalog.name = "Old Name"
    source_part = add_part(source, part_num="3024")
    target_part = add_part(target, part_num="3024")
    source_color = add_color(source, external_id=0)
    target_color = add_color(target, external_id=0)
    add_set_part_inventory_line(
        session=source,
        catalog_set=source_catalog,
        part=source_part,
        color=source_color,
        quantity=8,
    )
    add_set_part_inventory_line(
        session=target,
        catalog_set=target_catalog,
        part=target_part,
        color=target_color,
        quantity=4,
    )
    add_owned_set(target, target_catalog, with_inventory=True)
    source.commit()
    target.commit()

    result = import_from_database_session(target, source, mode="add_and_update")
    target.commit()

    assert result.sets_updated == 1
    assert result.sets_added == 0
    target.refresh(target_catalog)
    assert target_catalog.name == "Updated Name"
    assert target_catalog.theme_id == target_theme.id
    assert target_catalog.image_blob == TINY_PNG


def test_add_and_update_preserves_age_labels_and_missing() -> None:
    source = _make_session()
    target = _make_session()
    source_catalog, _ = _populate_source_set(
        source,
        set_number=6024,
        age=4,
        label="Source Label",
        quantity_missing=0,
    )
    target_catalog = add_catalog_set(target, set_number=6024, set_variant=1)
    target_catalog.name = "Keep"
    source_line = source_catalog.set_part_inventory_lines[0]
    target_part = add_part(target, part_num="3024")
    target_color = add_color(target, external_id=0)
    target_line = add_set_part_inventory_line(
        session=target,
        catalog_set=target_catalog,
        part=target_part,
        color=target_color,
        quantity=4,
    )
    target_owned = add_owned_set(
        target, target_catalog, label="My Label", with_inventory=False
    )
    target_owned.age = 8
    target_instance = OwnedSetInventoryLine(
        owned_set_id=target_owned.id,
        set_part_inventory_line_id=target_line.id,
        quantity=4,
        quantity_missing=2,
    )
    target.add(target_instance)
    target.flush()
    from app.db.models import MissingItem

    target.add(
        MissingItem(
            owned_set_id=target_owned.id,
            owned_set_inventory_line_id=target_instance.id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
    )
    source.commit()
    target.commit()

    import_from_database_session(target, source, mode="add_and_update")
    target.commit()

    target.refresh(target_owned)
    target.refresh(target_instance)
    assert target_owned.label == "My Label"
    assert target_owned.age == 8
    assert target_instance.quantity_missing == 2


def test_add_and_update_fills_null_age_from_source() -> None:
    source = _make_session()
    target = _make_session()
    source_catalog, _ = _populate_source_set(source, set_number=6024, age=6, label=None)
    target_catalog = add_catalog_set(target, set_number=6024, set_variant=1)
    source_line = source_catalog.set_part_inventory_lines[0]
    target_part = add_part(target, part_num="3024")
    target_color = add_color(target, external_id=0)
    add_set_part_inventory_line(
        session=target,
        catalog_set=target_catalog,
        part=target_part,
        color=target_color,
        quantity=source_line.quantity,
    )
    target_owned = add_owned_set(target, target_catalog, with_inventory=True)
    target_owned.age = None
    source.commit()
    target.commit()

    import_from_database_session(target, source, mode="add_and_update")
    target.commit()

    target.refresh(target_owned)
    assert target_owned.age == 6


def test_new_set_import_copies_parts_and_missing() -> None:
    source = _make_session()
    target = _make_session()
    _populate_source_set(
        source,
        set_number=7777,
        label="Imported Copy",
        quantity_missing=1,
    )
    source.commit()

    result = import_from_database_session(target, source, mode="add_only_new")
    target.commit()

    assert result.sets_added == 1
    assert result.instances_created == 1
    part = target.scalar(select(Part).where(Part.part_num == "3024"))
    assert part is not None
    assert part.image_blob == TINY_PNG
    owned = target.scalar(select(OwnedSet))
    assert owned is not None
    assert owned.label == "Imported Copy"
    instance = target.scalar(select(OwnedSetInventoryLine))
    assert instance is not None
    assert instance.quantity_missing == 1
