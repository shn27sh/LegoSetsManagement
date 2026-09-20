"""ORM models matching docs/database-schema.md."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Theme(Base):
    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    catalog_sets: Mapped[list[CatalogSet]] = relationship(back_populates="theme")


class CatalogSet(Base):
    """Shared metadata and inventory **template** for one LEGO catalog set.

    `set_number` is the user-visible integer (e.g. 65001). `set_variant` is the Rebrickable
    suffix (usually 1); HTTP calls use ``{set_number}-{set_variant}``.

    In the product, this is not a wishlist row: it exists only because the user has at least
    one physical copy (`OwnedSet`). Deleting the user's last copy removes this catalog stub.
    """

    __tablename__ = "catalog_sets"
    __table_args__ = (
        UniqueConstraint("set_number", "set_variant", name="uq_catalog_sets_number_variant"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    set_number: Mapped[int] = mapped_column(Integer, nullable=False)
    set_variant: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    theme_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("themes.id"), nullable=True
    )
    num_parts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    theme: Mapped[Theme | None] = relationship(back_populates="catalog_sets")
    owned_sets: Mapped[list[OwnedSet]] = relationship(back_populates="catalog_set")
    set_part_inventory_lines: Mapped[list[SetPartInventoryLine]] = relationship(
        back_populates="catalog_set"
    )
    set_minifig_inventory_lines: Mapped[list[SetMinifigInventoryLine]] = relationship(
        back_populates="catalog_set"
    )


class OwnedSet(Base):
    """One physical LEGO set **copy** stored in the user's collection (`owned_sets` table).

    Product rule: the database never represents LEGO sets outside the user's collection.
    `catalog_sets` holds shared metadata for a LEGO set number (`set_number`) and exists only while at least
    one copy row points to it; deleting the last copy cascades away that catalog.
    """

    __tablename__ = "owned_sets"
    __table_args__ = (
        Index("ix_owned_sets_catalog_set_id", "catalog_set_id"),
        Index("ix_owned_sets_investigated", "investigated"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_set_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("catalog_sets.id"), nullable=False
    )
    investigated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    catalog_set: Mapped[CatalogSet] = relationship(back_populates="owned_sets")
    inventory_lines: Mapped[list[OwnedSetInventoryLine]] = relationship(
        back_populates="owned_set", cascade="all, delete-orphan"
    )
    missing_items: Mapped[list[MissingItem]] = relationship(
        back_populates="owned_set", cascade="all, delete-orphan"
    )


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_num: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    part_image_user_removed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    aliases: Mapped[list[PartAlias]] = relationship(back_populates="part")
    set_part_inventory_lines: Mapped[list[SetPartInventoryLine]] = relationship(
        back_populates="part"
    )
    minifig_part_inventory_lines: Mapped[list[MinifigPartInventoryLine]] = relationship(
        back_populates="part"
    )
    part_color_keys: Mapped[list[PartColorKey]] = relationship(
        back_populates="anchor_part"
    )


class PartAlias(Base):
    __tablename__ = "part_aliases"
    __table_args__ = (
        UniqueConstraint(
            "part_id", "alias", "source", name="uq_part_aliases_part_alias_source"
        ),
        Index("ix_part_aliases_alias", "alias"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_id: Mapped[int] = mapped_column(Integer, ForeignKey("parts.id"), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)

    part: Mapped[Part] = relationship(back_populates="aliases")


class Color(Base):
    __tablename__ = "colors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    rgb: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    set_part_inventory_lines: Mapped[list[SetPartInventoryLine]] = relationship(
        back_populates="color"
    )
    minifig_part_inventory_lines: Mapped[list[MinifigPartInventoryLine]] = relationship(
        back_populates="color"
    )
    part_color_keys: Mapped[list[PartColorKey]] = relationship(back_populates="color")


class PartColorKey(Base):
    """Canonical identity for a colored part (alias class + color), shared across sets."""

    __tablename__ = "part_color_keys"
    __table_args__ = (
        UniqueConstraint(
            "anchor_part_id",
            "color_id",
            name="uq_part_color_keys_anchor_color",
        ),
        Index("ix_part_color_keys_color_id", "color_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    anchor_part_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("parts.id"), nullable=False
    )
    color_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("colors.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    anchor_part: Mapped[Part] = relationship(back_populates="part_color_keys")
    color: Mapped[Color] = relationship(back_populates="part_color_keys")
    element_ids: Mapped[list[PartColorElementId]] = relationship(
        back_populates="part_color_key", cascade="all, delete-orphan"
    )


class PartColorElementId(Base):
    __tablename__ = "part_color_element_ids"
    __table_args__ = (
        UniqueConstraint(
            "part_color_key_id",
            "element_id",
            name="uq_part_color_element_ids_key_element",
        ),
        Index("ix_part_color_element_ids_element_id", "element_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    part_color_key_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("part_color_keys.id", ondelete="CASCADE"), nullable=False
    )
    element_id: Mapped[str] = mapped_column(Text, nullable=False)

    part_color_key: Mapped[PartColorKey] = relationship(back_populates="element_ids")


class SetPartInventoryLine(Base):
    __tablename__ = "set_part_inventory_lines"
    __table_args__ = (
        UniqueConstraint(
            "catalog_set_id",
            "part_id",
            "color_id",
            name="uq_set_part_inventory_lines_natural_key",
        ),
        CheckConstraint("quantity > 0", name="ck_set_part_inventory_lines_quantity"),
        Index("ix_set_part_inventory_lines_catalog_set_id", "catalog_set_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_set_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("catalog_sets.id"), nullable=False
    )
    part_id: Mapped[int] = mapped_column(Integer, ForeignKey("parts.id"), nullable=False)
    color_id: Mapped[int] = mapped_column(Integer, ForeignKey("colors.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    catalog_set: Mapped[CatalogSet] = relationship(back_populates="set_part_inventory_lines")
    part: Mapped[Part] = relationship(back_populates="set_part_inventory_lines")
    color: Mapped[Color] = relationship(back_populates="set_part_inventory_lines")
    instance_inventory_lines: Mapped[list[OwnedSetInventoryLine]] = relationship(
        back_populates="set_part_inventory_line"
    )


class CatalogMinifig(Base):
    __tablename__ = "catalog_minifigs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    minifig_num: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    set_minifig_inventory_lines: Mapped[list[SetMinifigInventoryLine]] = relationship(
        back_populates="catalog_minifig"
    )
    minifig_part_inventory_lines: Mapped[list[MinifigPartInventoryLine]] = relationship(
        back_populates="catalog_minifig"
    )


class SetMinifigInventoryLine(Base):
    __tablename__ = "set_minifig_inventory_lines"
    __table_args__ = (
        UniqueConstraint(
            "catalog_set_id",
            "catalog_minifig_id",
            name="uq_set_minifig_inventory_lines_natural_key",
        ),
        CheckConstraint("quantity > 0", name="ck_set_minifig_inventory_lines_quantity"),
        Index("ix_set_minifig_inventory_lines_catalog_set_id", "catalog_set_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_set_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("catalog_sets.id"), nullable=False
    )
    catalog_minifig_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("catalog_minifigs.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    catalog_set: Mapped[CatalogSet] = relationship(back_populates="set_minifig_inventory_lines")
    catalog_minifig: Mapped[CatalogMinifig] = relationship(
        back_populates="set_minifig_inventory_lines"
    )


class MinifigPartInventoryLine(Base):
    __tablename__ = "minifig_part_inventory_lines"
    __table_args__ = (
        UniqueConstraint(
            "catalog_minifig_id",
            "part_id",
            "color_id",
            name="uq_minifig_part_inventory_lines_natural_key",
        ),
        CheckConstraint("quantity > 0", name="ck_minifig_part_inventory_lines_quantity"),
        Index("ix_minifig_part_inventory_lines_catalog_minifig_id", "catalog_minifig_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    catalog_minifig_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("catalog_minifigs.id"), nullable=False
    )
    part_id: Mapped[int] = mapped_column(Integer, ForeignKey("parts.id"), nullable=False)
    color_id: Mapped[int] = mapped_column(Integer, ForeignKey("colors.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    catalog_minifig: Mapped[CatalogMinifig] = relationship(
        back_populates="minifig_part_inventory_lines"
    )
    part: Mapped[Part] = relationship(back_populates="minifig_part_inventory_lines")
    color: Mapped[Color] = relationship(back_populates="minifig_part_inventory_lines")
    instance_inventory_lines: Mapped[list[OwnedSetInventoryLine]] = relationship(
        back_populates="minifig_part_inventory_line"
    )


class ElementImage(Base):
    __tablename__ = "element_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    element_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    image_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    image_content_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_byte_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OwnedSetInventoryLine(Base):
    __tablename__ = "owned_set_inventory_lines"
    __table_args__ = (
        CheckConstraint(
            "(set_part_inventory_line_id IS NOT NULL AND minifig_part_inventory_line_id IS NULL) "
            "OR (set_part_inventory_line_id IS NULL AND minifig_part_inventory_line_id IS NOT NULL)",
            name="ck_owned_set_inventory_lines_one_line_ref",
        ),
        CheckConstraint("quantity > 0", name="ck_owned_set_inventory_lines_quantity"),
        CheckConstraint(
            "quantity_missing >= 0 AND quantity_missing <= quantity",
            name="ck_owned_set_inventory_lines_missing",
        ),
        Index(
            "uq_owned_set_inventory_lines_owned_set_part",
            "owned_set_id",
            "set_part_inventory_line_id",
            unique=True,
            sqlite_where=text("set_part_inventory_line_id IS NOT NULL"),
        ),
        Index(
            "uq_owned_set_inventory_lines_owned_minifig_part",
            "owned_set_id",
            "minifig_part_inventory_line_id",
            unique=True,
            sqlite_where=text("minifig_part_inventory_line_id IS NOT NULL"),
        ),
        Index("ix_owned_set_inventory_lines_owned_set_id", "owned_set_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owned_set_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("owned_sets.id", ondelete="CASCADE"), nullable=False
    )
    set_part_inventory_line_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("set_part_inventory_lines.id", ondelete="CASCADE"),
        nullable=True,
    )
    minifig_part_inventory_line_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("minifig_part_inventory_lines.id", ondelete="CASCADE"),
        nullable=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_missing: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )

    owned_set: Mapped[OwnedSet] = relationship(back_populates="inventory_lines")
    set_part_inventory_line: Mapped[SetPartInventoryLine | None] = relationship(
        back_populates="instance_inventory_lines"
    )
    minifig_part_inventory_line: Mapped[MinifigPartInventoryLine | None] = relationship(
        back_populates="instance_inventory_lines"
    )
    missing_item: Mapped[MissingItem | None] = relationship(
        back_populates="owned_set_inventory_line",
        uselist=False,
        cascade="all, delete-orphan",
    )


class MissingItem(Base):
    __tablename__ = "missing_items"
    __table_args__ = (
        Index(
            "uq_missing_items_owned_set_inventory_line",
            "owned_set_inventory_line_id",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owned_set_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("owned_sets.id", ondelete="CASCADE"), nullable=False
    )
    owned_set_inventory_line_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("owned_set_inventory_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    owned_set: Mapped[OwnedSet] = relationship(back_populates="missing_items")
    owned_set_inventory_line: Mapped[OwnedSetInventoryLine] = relationship(
        back_populates="missing_item"
    )
