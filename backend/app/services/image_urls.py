"""Build API URLs for locally stored image BLOBs."""


def part_image_url(part_id: int) -> str:
    return f"/api/parts/{part_id}/image"


def catalog_set_image_url(catalog_set_id: int) -> str:
    return f"/api/catalog-sets/{catalog_set_id}/image"


def catalog_minifig_image_url(catalog_minifig_id: int) -> str:
    return f"/api/catalog-minifigs/{catalog_minifig_id}/image"


def missing_part_image_url(part_id: int) -> str:
    """Legacy route that resolves missing row → part image."""
    return f"/api/media/missing/part/{part_id}"


def element_image_url(element_id: str) -> str:
    return f"/api/elements/{element_id}/image"


def pick_display_image_url(*, local_url: str | None) -> str | None:
    return local_url
