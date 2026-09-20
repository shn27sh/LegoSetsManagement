# Data sources — LEGO Collection Manager (MVP)

This document defines **file** and **network** inputs: formats, environment variables, Rebrickable resources used, and mapping principles into the local database. It complements [product-requirements.md](./product-requirements.md) and [database-schema.md](./database-schema.md).

## CSV import (collection set numbers)

### Format

| Aspect | Rule |
|--------|------|
| **Encoding** | UTF-8 only. |
| **Structure** | A **plain text** file: Rebrickable-compatible **set numbers** separated by **commas**. There is **no header row** and **no column layout** (not a spreadsheet schema). |
| **Separators** | Comma (`,`). Tokens may also be separated by **whitespace** and **newlines**; the parser normalizes by splitting on commas and whitespace runs, then trimming each token. |
| **Example** | `6024`, `6024-1`, `10281-2` or multi-line: `6024, 10281-1\n21309-1` |
| **Minimum content** | At least one non-empty set number token per successful import. |

### Normalization

- Trim leading and trailing whitespace on every token.
- Empty token after trim → token error, skip token.
- **Base number vs variant:** Rebrickable’s HTTP API uses strings like `6024-1` (base **6024**, variant **1**). Users may enter **only the base number** (e.g. `6024`); the app assumes variant **`1`** when building the Rebrickable key. Users may also enter an explicit variant (`6024-2`, `65001-3`). The database stores **`set_number`** (integer) and **`set_variant`** (integer); the UI and collection JSON expose **only the base number** as `set_num`.
- **Case:** digits-only tokens are case-insensitive only insofar as they are numeric; preserve explicit `base-variant` input after trim.
- If the API returns 404 for the resolved key, surface that as a **sync-time** or **import-time** error for that token (see import API).

### Semantics

- **One token → one new physical copy:** each valid set number in the file creates a **new** row in `owned_sets`, linked to the shared `catalog_sets` row for that **number + variant**. Repeating the same token in one file or across imports creates **multiple copies** (see [product-requirements.md](./product-requirements.md)).
- Import is **additive** only: it never removes existing copies.
- Re-uploading an identical file will create **additional duplicate copies**; the app does not deduplicate across imports.

### MVP vs Phase 12 (CSV + Rebrickable)

| Aspect | MVP (Phases 1–8) | Phase 12+ |
|--------|------------------|-----------|
| Catalog row on CSV | **Stub** (`name` NULL, etc.) until sync | **Full fetch** per token via Rebrickable APIs |
| Inventory | Filled by `POST /imports/rebrickable/sync` | Filled during CSV import (same endpoints as sync, mocked in tests) |
| Images | Downloaded on CSV import | CSV import downloads set, minifigure, and part images into SQLite after each successful catalog fetch; Rebrickable sync can optionally refresh them |
| API key | Optional for CSV alone | **Required** for CSV import |

### Investigation default

New **`owned_sets`** rows created from **CSV import** or **`POST /owned-sets/{id}/duplicate`** have `investigated = false` until the user marks them investigated in the UI or API.

### Failed sets retry file (`failedSets.csv`)

| Aspect | Rule |
|--------|------|
| **When written** | Start of each **`POST /imports/csv`** or **`POST /imports/rebrickable/sync`** clears the file; catalog fetch failures during that run are collected at the end. |
| **Format** | Same as CSV import input: UTF-8, comma-separated Rebrickable keys (`6024-1`), no header. |
| **Contents** | Only sets that failed with **`RebrickableAPIError`** (e.g. HTTP 404). Not parse errors, not image CDN failures. |
| **Download** | **`GET /imports/failed-sets.csv`** (see [api-design.md](./api-design.md)). |
| **Env** | `FAILED_SETS_CSV_PATH` (default `./data/failedSets.csv`). |

## Database import (second SQLite file)

| Aspect | Rule |
|--------|------|
| **Format** | SQLite file (`.db`) produced by another install of this app (same schema; must contain `catalog_sets`). |
| **Transport** | `multipart/form-data` upload on **`POST /imports/database`** with field `file` and `mode`. |
| **Max size** | 500 MB default (`DATABASE_IMPORT_MAX_BYTES`). |
| **Matching** | Catalog sets by **`(set_number, set_variant)`**; parts by `part_num`; inventory lines by catalog line keys. |
| **`add_only_new`** | Copy sets (and dependent catalog rows, inventory, images) that are not already in the target DB. |
| **`add_and_update`** | Same for new sets; for existing sets, refresh catalog/inventory/images. **Do not overwrite** target per-copy **age** (when any copy has age), **theme** (when target catalog already has theme), **labels**, or **missing** state. |
| **Network** | None; offline merge only. |

See [api-design.md](./api-design.md) for the response shape and [product-requirements.md §2b](./product-requirements.md#2b-import-from-another-database-file).

## Rebrickable API

### Official documentation

- Base URL and versioning: **`https://rebrickable.com/api/v3/`** (HTTPS only).
- Human-readable API reference: [https://rebrickable.com/api/](https://rebrickable.com/api/)

Prefer documented endpoints only; do not rely on undocumented HTML scraping.

### Authentication

| Variable | Purpose |
|----------|---------|
| `REBRICKABLE_API_KEY` | API key sent with each request per Rebrickable’s documented auth scheme (typically an `Authorization` header or key query parameter—follow the official docs at implementation time). |

Rules:

- Never commit real keys; document `REBRICKABLE_API_KEY` in **`.env.example`** with a placeholder.
- Missing key → clear configuration error before any network call.

### MVP endpoint set

The following **REST** resources are in scope for MVP. Exact paths and query parameters must match the published Rebrickable v3 docs at implementation time.

| Resource (conceptual) | HTTP | Purpose | Populates / updates |
|------------------------|------|-----------|----------------------|
| Set metadata | `GET /lego/sets/{set_num}/` | Fetch one set’s catalog fields | `catalog_sets`, themes linkage |
| Set parts inventory | `GET /lego/sets/{set_num}/parts/` | Paginated parts in set with color, qty, spare, alt flags | `parts`, `part_aliases`, `colors`, `set_part_inventory_lines` |
| Set minifigs | `GET /lego/sets/{set_num}/minifigs/` | Minifigs included in set | `catalog_minifigs`, `set_minifig_inventory_lines` |
| Minifig parts | `GET /lego/minifigs/{minifig_num}/parts/` | BOM for one minifig | `parts`, `colors`, `minifig_part_inventory_lines` |
| Colors (optional batch) | `GET /lego/colors/` | Full color list for FK resolution and display | `colors` |
| Themes | Local `data/themes.csv`, with API fallback when missing | Parent theme name for display | `themes` + `catalog_sets.theme_id` |

**Pagination:** Rebrickable list endpoints are paginated; the importer must follow `next` links or page cursors until exhaustion (per official response schema).

### Rate limits and etiquette

- Respect Rebrickable **rate limits** and terms of use documented on their site.
- Implementation should use conservative concurrency (MVP: **sequential** requests per set are acceptable), with optional exponential backoff on `429` / transient `5xx`.
- Log request failures with enough context for debugging (without logging secrets).

### Mapping principles (catalog → SQLite)

General rules (details in [database-schema.md](./database-schema.md)):

| Rebrickable concept | Storage rule |
|---------------------|--------------|
| `set_num` | Primary business key for `catalog_sets`; many `owned_sets` may reference one `catalog_set_id`. |
| `part` / `part_num` | Upsert `parts`; store `name`, `part_img_url` or equivalent as returned. |
| `color_id` | Upsert `colors`; FK on inventory lines. |
| Quantity | Store on the appropriate inventory line table. |
| `is_spare`, `is_alternate` (set parts) | Parsed from Rebrickable DTOs; **not persisted**. Rows with either flag set are skipped during catalog import (`include_set_part_line` / `include_minifig_part_line` in `backend/app/importers/rebrickable_inventory_filters.py`). |
| `is_spare` (minifig BOM) | Parsed from Rebrickable; **not persisted** (spare BOM lines skipped on import). |
| Stickered vs plain | When Rebrickable uses different `part_num` values, store as **distinct** `parts` and distinct inventory lines—**no merging** in MVP. |
| Minifig `minifig_num` | Upsert `catalog_minifigs`; set-level minifig rows go to `set_minifig_inventory_lines`; BOM rows go to `minifig_part_inventory_lines`. |
| Aliases | When the API exposes alternate part IDs or legacy numbers, populate `part_aliases` so search remains accurate. |

### LEGO Element IDs

LEGO instruction manuals commonly identify a specific part/color combination by
**Element ID**. Rebrickable set inventory responses provide `part_num` and
`color_id` separately, so import/sync enriches inventory lines from the local
`data/elements.csv` file (`element_id,part_num,color_id,design_id`).

Rules:

- `data/elements.csv` is read only during import/sync or migration backfill.
- Override the import-time path with `ELEMENTS_CSV_PATH` when running from a
  non-standard checkout or in tests.
- Matching uses Rebrickable `part_num` plus Rebrickable external `color_id`, with alias and mold-variant fallbacks (`element_ids_for_import`).
- Multiple Element IDs for one part/color are valid and are stored on the canonical **`part_color_element_ids`** row for that alias class + color.
- Set detail and search read persisted Element IDs from **`part_color_keys`** / **`part_color_element_ids`**; they do not read the CSV at request time.
- Updating Element IDs during import/sync or a future manual edit updates the canonical colored-part record; all sets with that part + color see the change immediately.
- When Rebrickable sync runs with part-image download enabled, element image bytes
  from inventory line CDN URLs are stored in **`element_images`** keyed by Element ID
  (primary ID on each line). This enables color-specific thumbnails for the same
  `part_num` in different colors.

### LEGO themes

Rebrickable set responses provide a `theme_id` that can be a subtheme (for
example `Farm`). First-time import resolves that id through the local
`data/themes.csv` file (`id,name,parent_id`) and stores the parent theme when one
exists (for example `City`). If the CSV is missing or cannot resolve the id, the
importer falls back to `GET /lego/themes/{id}/`.

Rules:

- `data/themes.csv` is read only during first-time import and Rebrickable draft
  preview.
- Override the import-time path with `THEMES_CSV_PATH` when running from a
  non-standard checkout or in tests.
- Set detail reads the persisted theme from SQLite; it does not read the CSV at
  request time.

### Source metadata

Every upserted row that originates from Rebrickable should set at least:

- `source` = `rebrickable`
- `source_ref` = stable external identifier (e.g. set_num, part_num, minifig_num) as appropriate
- `fetched_at` = UTC timestamp of successful write

Optional later: payload hash for change detection.

## Catalog metadata (dual source)

Except for the per-copy **`label`** (user-only), set-level metadata may come from **Rebrickable sync**, from **CSV import** (set number only, leaving other fields empty until sync or manual entry), or from **user edit** on the set detail form (`PATCH /owned-sets/{id}`).

| Field | Storage | Rebrickable sync | User PATCH (detail form) |
|-------|---------|------------------|---------------------------|
| Set number | `catalog_sets.set_num` | Set API | `set_num` (this copy only; UI warning) |
| Name | `catalog_sets.name` | Set API | `catalog_name` |
| Theme | `themes` + `catalog_sets.theme_id` | Set API `theme_id`, resolved through `themes.csv` parent when available | `catalog_theme_name` (creates/links theme when none) |
| Year | `catalog_sets.year` | Set API | `catalog_year` |
| Part count | `catalog_sets.num_parts` | Set API | `catalog_num_parts` |
| Age | `owned_sets.age` (shared per `catalog_set_id`) | Set API **`age_range` only when present** (parsed to integer, e.g. `6+` → `6`). **Often absent** on older sets and many API payloads — sync/import **never overwrites** a user-entered age with NULL. | **`age`** on set detail (`PATCH`): user enters minimum age manually (box, LEGO product page, etc.) |
| Box image URL | `catalog_sets.image_url` | Set API | Not editable in MVP UI |

**User-only instance fields** (not populated from Rebrickable): `label`, `notes`, `investigated`.

**Re-sync behavior:** each successful Rebrickable sync updates the fields that are safe to refresh from the source: set name, set image URL/BLOB when requested, number of parts, part names/images, catalog inventory lines, and per-copy part quantities. Sync preserves theme, year, age, investigated, missing quantities/items, labels, and notes.

**Local metadata update:** the Import page includes a no-network maintenance action
that fills only missing fields. `data/age.csv` supplies `owned_sets.age` for
copies where age is currently unknown (`?`); values such as `7+` are stored as
`7`. `data/sets.csv` supplies a set's `theme_id`, and `data/themes.csv` resolves
that id to the stored theme, using the parent theme when `parent_id` is present.
Existing age and theme values are preserved.

## User-provided images (Phase 10+)

User photos are stored as **BLOBs in SQLite**, not on disk:

| Storage | Table | Scope |
|---------|-------|--------|
| Element image | `element_images` (`image_blob`, …) | **Per Element ID** — color-specific display for inventory lines; populated by sync (part-image download modes) and missing-part upload when element IDs exist. |
| Part image | `parts` (`image_blob`, `image_content_type`, `image_byte_size`) | **Global fallback** — one image per part; used when no element BLOB exists; target of **PartLineModal** part-photo uploads. |
| Set box image | `catalog_sets` (same BLOB columns) | **Shared** across all owned instances of that set. |
| Minifigure image | `catalog_minifigs` (same BLOB columns) | **Shared** per minifig design. |

Rules:

- Accepted formats: **JPEG** and **PNG**; max **5 MB** per [api-design.md](./api-design.md); min size **0** allowed.
- Missing-part upload (`PUT .../missing/{id}/image`) writes **`element_images`** when the line has persisted Element IDs, otherwise the **`parts`** BLOB.
- `GET /media/missing/{missing_item_id}` serves the resolved line image (element first, else part) when missing quantity > 0.
- Rebrickable CDN URLs on inventory lines are **never** returned to clients; they are download sources during sync only.
- No `UPLOAD_ROOT`, `MEDIA_ROOT`, or thumbnail/cache folders required for normal operation.
- Images are **not** sent to Rebrickable.

## Testing constraint

**All HTTP calls to Rebrickable must be mocked in automated tests.** Tests use fixture JSON aligned with the official response shapes; no real network calls. See [testing-strategy.md](./testing-strategy.md).

## Related documents

- [README.md](./README.md) — index of all specification files in `docs/`
- [product-requirements.md](./product-requirements.md)
- [database-schema.md](./database-schema.md)
- [api-design.md](./api-design.md)
