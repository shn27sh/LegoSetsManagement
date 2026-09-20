# API design — LEGO Collection Manager (MVP)

REST **JSON** API served by **FastAPI** for the **React + Vite** frontend. All paths below are relative to a configurable API root (e.g. `/api`); examples omit prefix for clarity.

## Conventions

| Topic | Choice |
|-------|--------|
| **Format** | `Content-Type: application/json` for bodies; UTF-8. |
| **Naming** | Plural path segment **`/owned-sets`** = **set copies** in the collection; JSON may still use `owned_set_*` field names. |
| **IDs** | Integer primary keys exposed as `id` unless noted. |
| **Timestamps** | ISO 8601 UTC strings in JSON. |
| **Pagination** | `limit` (default 50, max 200) + `offset` (default 0) on list endpoints. |
| **Errors** | FastAPI default shape: `{"detail": ...}` where `detail` is a string or list of validation objects. |

### HTTP status usage

| Code | When |
|------|------|
| `200` | Success with body. |
| `400` | Validation (bad query, impossible missing quantity, invalid image type). |
| `404` | Unknown `id` or resource. |
| `409` | Conflict (rare). |
| `413` | Upload too large. |
| `422` | Request body schema validation (Pydantic). |
| `503` | Upstream Rebrickable unreachable after retries (optional; may also map to `502`). |

**App modes (Phase 18):** View / Investigate / Edit are enforced in the **frontend UI** only for MVP. The REST API does not require mode headers or tokens. A future Edit password may add client-side gating first, then optional server-side tokens if the API is exposed beyond localhost.

## Import operations

### Background import jobs

Long-running imports run in a **background worker thread** so other API routes stay responsive. Only **one** job may be `queued` or `running` at a time per server process.

**`POST /imports/jobs`** — **`202`**

- **Body:** `multipart/form-data` with required `kind`: `csv` | `rebrickable_sync` | `database`.
- **`csv`:** `file` (same rules as `POST /imports/csv`), optional `existing_set_mode` (`skip` default).
- **`rebrickable_sync`:** optional `sync_options` form field — JSON object with the same fields as `POST /imports/rebrickable/sync` (omit for defaults).
- **`database`:** `file` (SQLite `.db`), optional `mode` (`add_only_new` | `add_and_update`).
- **Response:** `{ "job_id": "<uuid>", "status": "queued" }`.
- **Errors:** **`409`** if another job is active; **`400`** / **`413`** same validation as synchronous import routes.

**`GET /imports/jobs/active`**

- **Response `200`:** Same shape as `GET /imports/jobs/{job_id}` for the single queued or running job in this server process.
- **Response `404`:** No job is queued or running. The Import UI uses this (and `sessionStorage`) to restore progress after navigation.

**`GET /imports/jobs/{job_id}`**

- **Response `200`:** `{ "job_id", "kind", "status", "progress": { "current", "total", "label" } | null, "result": {…} | null, "error": string | null, "failed_sets_csv_path": string | null }`.
- `status`: `queued` | `running` | `completed` | `failed` | `cancelled`.
- `result` shape matches the synchronous endpoint for that `kind` when `status` is `completed`.
- **`404`** if `job_id` is unknown.

**`DELETE /imports/jobs/{job_id}`**

- Requests **cooperative cancel** (checked between sets/tokens). Returns current job snapshot (same shape as `GET`).
- **`404`** if unknown.

**Legacy synchronous routes** (`POST /imports/csv`, `/rebrickable/sync`, `/database`) remain for existing clients and tests. The **Import** page and **set-detail sync** use the jobs API (start → poll → cancel) with progress UI and a link to `GET /imports/failed-sets.csv` when retry keys exist.

**CSV import jobs** fetch catalog data per token (`progress.label` like `Importing 6024-1`), then download set, minifigure, and part images for that token (`Downloading images for 6024-1`). **Rebrickable sync jobs** run in two phases when image download options are enabled: catalog API fetch per set (`Syncing catalog 6024-1`), then CDN image downloads (`Downloading images for 6024-1`). Image HTTP uses a **shared client** per job with `IMAGE_DOWNLOAD_MIN_INTERVAL_SECONDS` (default `0.3`) between requests — see `backend/.env.example`.

### Failed sets retry file

**`GET /imports/failed-sets.csv`**

- **Response `200`:** `text/plain; charset=utf-8` body — comma-separated Rebrickable set keys (e.g. `6024-1,9999-1`), no header, same token format as [data-sources.md](./data-sources.md) CSV import.
- **Response `404`:** File missing or empty (no catalog-level failures recorded for the last CSV import or Rebrickable sync).
- **Semantics:** Each **`POST /imports/csv`** or **`POST /imports/rebrickable/sync`** **replaces** the file at the start of the operation and writes only sets whose **Rebrickable catalog fetch** failed (`RebrickableAPIError`). Parse/token errors and image download failures are **not** included. Re-import the downloaded file via **`POST /imports/csv`** to retry.
- **Path:** `FAILED_SETS_CSV_PATH` (default `./data/failedSets.csv`; portable installs use the data directory — see `backend/.env.example`).

### CSV import — synchronous (additive)

**`POST /imports/csv`**

- **Body:** `multipart/form-data` with field `file` (plain text per [data-sources.md](./data-sources.md): comma-separated set numbers, no header) and optional `existing_set_mode`.
- **Max size:** 1 MB (MVP default; configurable server-side).
- **Behavior:** For each valid set-number **token**, new catalog sets are fetched from Rebrickable and create a first `owned_sets` row (`investigated` = `false`). Existing catalog sets are **skipped** by default (`existing_set_mode=skip`); the response lists each skipped token in `skipped_existing_sets`. The Import page always uses `skip`. API clients may pass `existing_set_mode=copy` to create a new physical copy from local catalog/inventory without fetching.

**Response `200`:**

```json
{
  "instances_created": 3,
  "catalog_stubs_created": 1,
  "existing_sets_skipped": 0,
  "skipped_existing_sets": [],
  "errors": [
    { "token_index": 4, "raw": "", "message": "empty set number" }
  ]
}
```

### Database import — synchronous

**`POST /imports/database`**

- **Body:** `multipart/form-data` with field `file` (SQLite `.db` from another LEGO Collection Manager install) and `mode` (`add_only_new` default, or `add_and_update`).
- **Max size:** 500 MB default (`DATABASE_IMPORT_MAX_BYTES` server-side).
- **Validation:** Source file must be SQLite with an `catalog_sets` table; otherwise **`400`**.
- **`add_only_new`:** Import catalog sets (and parts, inventory, images) whose `(set_number, set_variant)` are not already in the target database. Existing sets are skipped.
- **`add_and_update`:** Same for new sets; for existing sets, refresh catalog metadata, images, and inventory. **Preserves** per-copy **age** (when any copy already has age), **theme** (when catalog already has theme), **copy labels**, and **missing quantities/items**.

**Response `200`:**

```json
{
  "sets_added": 2,
  "sets_updated": 1,
  "sets_skipped": 3,
  "skipped_set_nums": ["6024-1", "8888-1"],
  "instances_created": 2,
  "parts_upserted": 120,
  "inventory_lines_written": 340
}
```

### Rebrickable sync — UI (jobs) and legacy synchronous route

**Primary UI path:** **Import** and **set detail** use **`POST /imports/jobs`** with `kind: rebrickable_sync` and optional `sync_options` JSON (same fields as the legacy body below). The client polls **`GET /imports/jobs/{job_id}`** (~1.5s interval), shows progress/cancel, and may download **`GET /imports/failed-sets.csv`** after catalog failures. See [Background import jobs](#background-import-jobs).

**Legacy synchronous route (API clients / tests):** **`POST /imports/rebrickable/sync`**

Returns **`200`** when the sync completes for the selected scope in the request thread. Prefer jobs for long-running work so the server stays responsive.

| Phase | What is shipped |
|-------|-----------------|
| **Phase 14 shipped** | Jobs-based sync on Import and set detail; progress/cancel; failed-sets retry file; set images **off** by default on Import sync. |
| **Phase 14 backlog** | Conflict policy with manual edits, richer subset selection from list views. |

| Tradeoff | Mitigation |
|----------|------------|
| Long legacy HTTP request | Use **`POST /imports/jobs`** from the UI; legacy route remains for scripts and tests. |
| Timeouts | Document recommended max **distinct `set_num`** per operation; pass explicit `owned_set_ids` in `sync_options` when scoping. |

**`POST /imports/rebrickable/sync` body:**

```json
{
  "owned_set_ids": [1, 2, 3],
  "download_set_images": true,
  "part_image_download_mode": "none"
}
```

Omit `owned_set_ids` or pass `null` to sync **every `set_num`** that has at least one `owned_sets` row (distinct `catalog_set_id` values may be synced once per `set_num` while updating shared catalog inventory). Sync updates set name, set image URL/BLOB when requested, number of parts, part names/images, catalog inventory lines, and per-copy part quantities. Sync preserves theme, year, age, investigated, missing quantities/items, labels, and notes. `download_set_images` stores set box images and minifigure images in SQLite. `part_image_download_mode` is one of `none` (default), `missing` (only parts currently marked missing, including minifig BOM parts), or `all` (all synced inventory parts, including minifig BOM parts). When part-image download is enabled, bytes are stored in **`element_images`** keyed by the colored part’s primary Element ID (requires persisted element IDs from `elements.csv` enrichment on the canonical **`part_color_*`** tables); the response counter remains `part_images_downloaded`.

`download_missing_part_images` is accepted as a legacy compatibility boolean only when `part_image_download_mode` is left at `none`; new clients should use `part_image_download_mode`.

**Response `200`:**

```json
{
  "sets_synced": 3,
  "sets_failed": [
    { "set_num": "0000-1", "message": "HTTP 404 from Rebrickable" }
  ],
  "parts_upserted": 1200,
  "inventory_lines_written": 3500,
  "set_images_downloaded": 3,
  "minifig_images_downloaded": 8,
  "part_images_downloaded": 42,
  "image_downloads_failed": [
    {
      "target": "element:302400",
      "url": "https://cdn.rebrickable.com/media/parts/elements/302400.jpg",
      "message": "HTTP 404"
    }
  ]
}
```

**Transactional rule:** Each set’s catalog fetch + inventory write runs in a **transaction**; failure for one set rolls back only that set’s writes (others committed)—exact granularity is implementation-defined but must avoid half-written inventory for a single `set_num`.

**Environment:** Requires `REBRICKABLE_API_KEY`; if missing, return **`400`** with clear `detail`.

### Local metadata update — synchronous

**`POST /imports/local-metadata`**

Fills missing local metadata without calling Rebrickable. The Import page exposes this below Rebrickable sync.

- Updates `owned_sets.age` only where age is currently missing (`NULL` / displayed as `?`), using `data/age.csv`; values such as `7+` are stored as `7`.
- Updates `catalog_sets.theme_id` only where the theme is currently unknown (`NULL` / displayed as `Unknown theme`), using `data/sets.csv` for the set theme id and `data/themes.csv` to resolve the display theme. If `parent_id` exists, the parent theme is stored.
- Existing age and theme values are preserved.

**Response `200`:**

```json
{
  "owned_set_ages_updated": 42,
  "catalog_themes_updated": 3,
  "age_values_available": 410,
  "theme_values_available": 26827
}
```

## Set copies (`GET/POST /owned-sets`, …)

Everything under this path is **a physical copy** in the user’s collection (table `owned_sets`). **`catalog_sets`** is shared metadata/template for the LEGO `set_num` and may be removed when the **last** copy is deleted.

### List set copies

**`GET /owned-sets?limit=50&offset=0&investigated=false`**

| Query param | Purpose |
|-------------|---------|
| `investigated` | Optional filter: `true` \| `false`. Omit for all. |
| `theme` | Repeatable. Filter by exact `themes.name` (case-sensitive). Omit for all themes. |
| `missing_only` | When `true`, only copies with at least one missing item. |
| `sort_by` | `created` \| `set_num` \| `name` \| `theme` \| `num_parts` \| `age` (default `created`). |
| `sort_dir` | `asc` \| `desc` (default `asc`). |

The sets list UI loads **all** rows matching these server filters (paginated API requests), then applies sort, group-by, and client-side pagination.

### Theme options (filter dropdown)

**`GET /owned-sets/theme-options`**

**Response `200`:**

```json
{ "themes": ["Classic Town", "Space"] }
```

Distinct theme names from owned sets in the collection (ordered case-insensitively). Used to populate the Theme multi-select on the sets list.

**Response `200`:**

```json
{
  "items": [
    {
      "id": 1,
      "set_num": "6024-1",
      "name": "Police Car",
      "year": 1980,
      "theme_name": "Classic Town",
      "image_url": "/api/catalog-sets/10/image",
      "catalog_sync_state": "ok",
      "investigated": false,
      "label": "eBay May 2026",
      "display_label": "eBay May 2026",
      "copy_index": 1,
      "age": 6,
      "num_parts": 27,
      "missing_count": 2
    }
  ],
  "total": 42
}
```

| Field | Notes |
|-------|--------|
| `display_label` | `label` if set, else `Copy #{copy_index}`. |
| `copy_index` | 1-based index among **copies** sharing `catalog_set_id` (order: `created_at`, `id`). |
| `name` | Catalog name; UI default **Unknown name** when null. |
| `theme_name` | UI default **Unknown theme** when null. |
| `num_parts` | From catalog; UI default **`?`** when null. |
| `age` | Integer; shared across **copies** of same catalog set when PATCHed; UI default **`?`** when null. Rebrickable `6+` → `6` on sync. |

`catalog_sync_state`: `ok` \| `pending` \| `error` (surface last sync issue for the underlying catalog set if stored).

Multiple `items` may share the same `set_num` with different `id`.

**List title (UI):** render `{display_label} — {set_num}`; secondary line: name, theme, parts, age with defaults above.

### Set copy detail

**`GET /owned-sets/{id}`**

**Response `200`:** nested structure for one screen load.

```json
{
  "id": 1,
  "investigated": false,
  "label": "eBay May 2026",
  "display_label": "eBay May 2026",
  "copy_index": 1,
  "age": null,
  "notes": null,
  "catalog": {
    "catalog_set_id": 10,
    "set_num": "6024-1",
    "name": "Police Car",
    "year": 1980,
    "theme_name": "Classic Town",
    "theme_shared_catalog_set_count": 2,
    "image_url": "/api/catalog-sets/10/image",
    "num_parts": 27
  },
  "inventory": {
    "set_parts": [
      {
        "instance_line_id": 100,
        "catalog_line_id": 9001,
        "part_id": 42,
        "part_num": "3024",
        "part_name": "Plate 1 x 1",
        "color_id": 0,
        "color_name": "Black",
        "quantity": 4,
        "element_ids": ["302400", "6252045"],
        "aliases": ["3024b", "3024pr"],
        "image_url": "/api/elements/302400/image",
        "part_image_url": null,
        "part_image_user_removed": false,
        "missing_quantity": 1,
        "missing_item_id": 501,
        "missing_image_url": "/api/elements/302400/image"
      }
    ],
    "minifigs": [
      {
        "line_id": 40,
        "catalog_minifig_id": 12,
        "minifig_num": "fig-000001",
        "name": "Police Officer",
        "image_url": "/api/catalog-minifigs/12/image",
        "quantity": 1,
        "parts": [
          {
            "instance_line_id": 200,
            "catalog_line_id": 9101,
            "part_id": 7,
            "part_num": "3626b",
            "part_name": "Minifig Head",
            "color_id": 14,
            "color_name": "Yellow",
            "quantity": 1,
            "element_ids": [],
            "image_url": null,
            "part_image_url": null,
            "part_image_user_removed": false,
            "missing_quantity": 0,
            "missing_item_id": null,
            "missing_image_url": null
          }
        ]
      }
    ]
  }
}
```

`quantity` and `missing_quantity` are **per copy** (`owned_set_inventory_lines`). `missing_quantity`, `missing_item_id`, and `missing_image_url` reflect **this copy’s** missing state.

**Inventory line images (set detail):**

| Field | Meaning |
|-------|---------|
| `element_ids` | Persisted LEGO Element IDs for this **colored part** (alias class + color), read from canonical `part_color_element_ids` — identical in every set that uses this part + color. |
| `image_url` | **Line display URL:** first persisted Element ID for this colored part with a local element BLOB (`/api/elements/{element_id}/image`), else the global part BLOB (`/api/parts/{part_id}/image`) when present, else `null`. |
| `part_image_url` | **Part BLOB only:** `/api/parts/{part_id}/image` when `parts.image_blob` exists, else `null` (never an element path). |
| `part_image_user_removed` | `true` after **`DELETE /parts/{part_id}/image`** (or equivalent clear) while element/catalog images may still exist; cleared on **`PUT /parts/{part_id}/image`**. |

The UI uses **`image_url`** for inventory list thumbnails, **Part view**, and **Edit part** preview (color-specific element first). **`part_image_url`** is the global part BLOB path only (upload target in Edit). **`part_image_user_removed`** records that the user cleared the global part BLOB; it does not hide element images on inventory lines.

All client-facing image fields are **same-origin API paths only** when a JPEG/PNG BLOB exists locally. Rebrickable CDN URLs stored in the database during sync are **not** exposed to clients — they are used only as download sources during import/sync.

`aliases` (Phase **11A**): other identifiers for this `part_id` from `part_aliases`, excluding strings equal to `part_num`. Omitted or empty when none. Read-only in detail until Phase **11B** enables editing via `PATCH /parts/{part_id}/aliases`.

**Catalog `image_url`:** `/api/catalog-sets/{catalog_set_id}/image` when a set BLOB exists locally; otherwise **null**.

### Update set copy (`PATCH`)

**`PATCH /owned-sets/{id}`**

All fields optional; omitted fields unchanged.

| Field | Type | Scope | Notes |
|-------|------|-------|--------|
| `investigated` | boolean | This copy | |
| `label` | string \| null | This copy | Empty string clears (stored NULL); UI default display `Copy #{copy_index}`. |
| `notes` | string \| null | This copy | |
| `age` | integer \| null | **All copies** with same `catalog_set_id` | Rebrickable sync may set from `age_range` (`6+` → `6`). |
| `set_num` | string | **This copy only** | Re-links to matching or new `catalog_sets` row; clears this copy’s missing items. UI warning required. |
| `catalog_name` | string \| null | **All copies** (catalog row) | |
| `catalog_theme_name` | string \| null | Catalog row (see `catalog_theme_scope`) | Creates or links a `themes` row when `theme_id` was NULL. |
| `catalog_theme_scope` | `"all"` \| `"this_set"` | With `catalog_theme_name` | Default **`all`**. See theme scope rules below. |
| `catalog_num_parts` | integer \| null | **All copies** (catalog row) | |
| `catalog_year` | integer \| null | **All copies** (catalog row) | |

Example (**this copy** + shared catalog fields):

```json
{
  "investigated": true,
  "label": "Copy #2",
  "age": 8,
  "notes": "Second-hand, box damaged",
  "catalog_name": "Police Car",
  "catalog_theme_name": "Town",
  "catalog_theme_scope": "this_set",
  "catalog_num_parts": 27,
  "catalog_year": 1980
}
```

**Theme rename scope** (with `catalog_theme_name`):

| `catalog_theme_scope` | Behavior |
|-----------------------|----------|
| **`all`** (default) | When other catalog sets share the same theme name (case-insensitive), rename the shared `themes` row in place, or merge all catalog sets on the source theme into an existing theme with the target name. |
| **`this_set`** | Re-link only this copy’s `catalog_sets` row to a separate theme (find-or-create by name); other catalog sets keep the previous theme. |

Detail **`catalog.theme_shared_catalog_set_count`** counts catalog sets in the collection whose theme name matches (case-insensitive). The UI shows an **Update theme?** dialog when this count is **> 1** and the user changes theme on save.

**Set number change:** send `set_num` only after UI warning; server re-links **this copy** to the matching or new `catalog_sets` row; other copies unchanged. Invalid or empty `set_num` → **400**.

**Response `200`:** same shape as list item fields for the updated copy.

### Delete set copy

**`DELETE /owned-sets/{id}`**

- Deletes the **`owned_sets` row** (one physical copy); cascades `missing_items` and `owned_set_inventory_lines`.
- If no other `owned_sets` reference the same `catalog_set_id`, delete that **catalog set and its inventory** as well.
- **`404`** if unknown id.
- **`200`** with `{ "deleted": true, "id": 1 }` on success.

### Duplicate set copy (“Make a copy”)

#### Preview (for confirmation dialog)

**`GET /owned-sets/{id}/duplicate-preview`**

**Response `200`:**

```json
{
  "source_owned_set_id": 1,
  "set_num": "6024-1",
  "set_name": "Police Car",
  "existing_copy_count": 2,
  "suggested_label": "Copy #3"
}
```

`suggested_label` = `Copy #{existing_copy_count + 1}`.

#### Create copy

**`POST /owned-sets/{id}/duplicate`**

**Body (optional):**

```json
{
  "label": "Copy #3"
}
```

If `label` is omitted, server uses `suggested_label` from the preview rules.

| Rule | Behavior |
|------|----------|
| `catalog_set_id` | Copied from source row |
| `investigated` | Always **`false`** |
| `label` | From request body or `Copy #n` default |
| `age`, `notes` | Copied from source (`age` may be **`null`** when source has no age) |
| `missing_items` | **None** on the new copy |
| Source row | Unchanged |

**Response `201`:** list-item shape plus `duplicated_from_owned_set_id`.

**`404`** if source `id` is unknown.

**UI:** list row **Make a copy** opens dialog using preview; **Create a copy** submits POST; **Cancel** discards.

## Images (SQLite BLOBs — Phase 10)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/elements/{element_id}/image` | Serve color-specific part image bytes (read-only) |
| `GET` | `/parts/{part_id}/image` | Serve part image bytes |
| `PUT` | `/parts/{part_id}/image` | Upload/replace (multipart `file`; max 5 MB; JPEG/PNG) |
| `DELETE` | `/parts/{part_id}/image` | Clear part image |
| `GET` | `/catalog-sets/{catalog_set_id}/image` | Serve set box image |
| `PUT` | `/catalog-sets/{catalog_set_id}/image` | Upload/replace set image |
| `DELETE` | `/catalog-sets/{catalog_set_id}/image` | Clear set image |
| `GET` | `/catalog-minifigs/{catalog_minifig_id}/image` | Serve minifigure image |
| `PUT` | `/catalog-minifigs/{catalog_minifig_id}/image` | Upload/replace minifigure image |
| `DELETE` | `/catalog-minifigs/{catalog_minifig_id}/image` | Clear minifigure image |

**Line display resolution:** `image_url` on inventory lines uses element BLOBs first, then part BLOBs. `part_image_url` is the part BLOB path only. **`DELETE /parts/{part_id}/image`** clears the part BLOB and sets `parts.part_image_user_removed`; element BLOBs are unchanged. **`GET /elements/{element_id}/image`** has no PUT/DELETE; sync and missing uploads may populate `element_images`, while **PartLineModal** part-photo uploads use **`PUT /parts/{part_id}/image`** on the global part row.

**`PUT` response `200`:** `{ "image_url": "/api/parts/{part_id}/image" }` (or catalog-set / catalog-minifig path).

**`DELETE` response `200`:** `{ "image_url": null }`.

**`GET`** returns raw bytes with stored `Content-Type`. **`404`** when no BLOB. **`413`** when upload exceeds size limit.

Detail JSON exposes `catalog.catalog_set_id`, line `part_id`, `image_url`, `part_image_url`, `part_image_user_removed`, and `catalog.image_url` as same-origin paths when BLOBs exist.

### Media (missing-line convenience)

**`GET /media/missing/{missing_item_id}`**

- Serves the **resolved line image** (element BLOB first, else part BLOB) for the inventory line linked to this missing row when `quantity_missing` > 0.
- **`404`** if unknown id, no missing quantity, or no local image BLOB.
- Prefer `GET /elements/{element_id}/image` or `GET /parts/{part_id}/image` for direct access; this route keeps older clients and `missing_image_url` working.

## Search

**`GET /search?q=3024&type=part&limit=20&offset=0`**

| Param | Values |
|-------|--------|
| `q` | Required, non-empty after trim. |
| `type` | `set` \| `part` \| `element` \| `all` (default `all`). |

**Semantics:**

- **`type=set`:** Match `catalog_sets.set_number` (string prefix on digits for MVP) for sets that have at least one `owned_sets` row; return **`owned_set_id`** values (**one per physical copy**; multiple copies sharing the same catalog set allowed).
- **`type=part`:** Match `parts.part_num` or `part_aliases.alias` (prefix); return **logical alias classes** that appear in the **catalog BOM** of at least one set in the collection (`set_part_inventory_lines` and minifig BOM lines). Each hit includes canonical **`part_num`**, **`name`**, resolved **`image_url`** (part BLOB only in MVP search — element BLOBs are used on set detail and reports), and **`lines`**: one row per actual **`parts.part_num`** in the alias class that has owned-set occurrences. Each line’s **`sets`** list includes catalog **`set_num`**, total template **`quantity`**, an **`owned_set_id`** link, and per-color quantities.
- **`type=element`:** Match persisted LEGO Element IDs (prefix); return one row per matched part/color combination. Each row includes the complete **`element_ids`** list for that part/color, related **`part_num`**, **`part_name`**, color display, and set occurrences.
- **`type=all`:** Return three buckets (`sets`, `parts`, `elements`).

**Example response (`type=set`):**

```json
{
  "sets": [
    {
      "owned_set_id": 1,
      "set_num": 6024,
      "name": "Police Car",
      "investigated": false,
      "label": "copy A"
    },
    {
      "owned_set_id": 7,
      "set_num": 6024,
      "name": "Police Car",
      "investigated": true,
      "label": "complete"
    }
  ],
  "parts": []
}
```

**Example fragment (`type=part`):** each logical part lists the canonical number and alias part numbers with their own per-set quantities (template BOM: set-level lines plus minifig counts × BOM qty).

```json
{
  "sets": [],
  "parts": [
    {
      "part_num": "15598",
      "name": "Plate 1 x 1",
      "image_url": "/api/parts/42/image",
      "lines": [
        {
          "display_part_num": "15598",
          "sets": [
            { "set_num": 65001, "quantity": 5, "owned_set_id": 3 },
            { "set_num": 30217, "quantity": 1, "owned_set_id": 4 }
          ]
        },
        {
          "display_part_num": "3069b",
          "sets": [
            { "set_num": 73605, "quantity": 1, "owned_set_id": 4 },
            { "set_num": 45001, "quantity": 2, "owned_set_id": 5 }
          ]
        }
      ]
    }
  ]
}
```

Empty `q` → **`400`**.

## Missing parts

### Upsert missing for a line

**`PATCH /owned-sets/{owned_set_id}/missing`**

Body (exactly one line reference):

```json
{
  "set_part_inventory_line_id": 9001,
  "quantity_missing": 2
}
```

or

```json
{
  "minifig_part_inventory_line_id": 9101,
  "quantity_missing": 1
}
```

**Rules:**

- `quantity_missing` ≥ 0. If `0`, **delete** existing missing row for that **set copy** + line (part BLOB is **not** cleared automatically).
- If > 0, must be ≤ `quantity` on the referenced inventory line (**400** if not).
- Creates `missing_items` row when needed; does not accept image bytes in this endpoint.

**Response `200`:**

```json
{
  "owned_set_id": 1,
  "missing_item_id": 501,
  "updated_lines": 1
}
```

### Upload or replace missing-part image

**`PUT /owned-sets/{owned_set_id}/missing/{missing_item_id}/image`**

- **Body:** `multipart/form-data`, field `file` (JPEG or PNG; max **5 MB**).
- **Behavior:** When the linked inventory line has persisted Element IDs, writes bytes to **`element_images`** for the primary Element ID; otherwise writes to the linked line’s **`parts`** row (`image_blob`, `image_content_type`, `image_byte_size`). Part-modal uploads still use **`PUT /parts/{part_id}/image`** directly.
- **`404`** if `missing_item_id` does not belong to `owned_set_id`.
- **`400`** if wrong content type or empty file.

**Response `200`:**

```json
{
  "missing_item_id": 501,
  "missing_image_url": "/api/elements/302400/image",
  "part_image_url": "/api/elements/302400/image"
}
```

### Remove missing-part image

**`DELETE /owned-sets/{owned_set_id}/missing/{missing_item_id}/image`**

- Clears the **element** or **part** BLOB used for display on that line (same resolution order as upload).
- Missing quantity row **remains** unless cleared via `PATCH .../missing` with `quantity_missing: 0`.

**Response `200`:**

```json
{
  "missing_item_id": 501,
  "missing_image_url": null,
  "part_image_url": null
}
```

### Optional read

Missing lines are embedded in **`GET /owned-sets/{id}`**; a dedicated `GET /owned-sets/{id}/missing` is **optional** if the detail payload becomes too heavy post-MVP.

---

## Post-MVP endpoints (Phases 9–10 — implemented)

### Per-copy inventory (Phase 9)

Detail payload (`GET /owned-sets/{id}`) exposes per-line **`quantity`** and **`missing_quantity`** for **this physical copy** (from `owned_set_inventory_lines`).

**`PATCH /owned-sets/{owned_set_id}/inventory-lines/{instance_line_id}`**

```json
{
  "quantity": 4,
  "quantity_missing": 2
}
```

- `quantity` > 0 when provided; `0 ≤ quantity_missing ≤ quantity` when provided.
- **`404`** if `instance_line_id` does not belong to this **`owned_sets` row** (this copy).
- Does not change other copies’ lines.

**`PATCH .../missing`** remains for missing-only updates using catalog line ids (`set_part_inventory_line_id` / `minifig_part_inventory_line_id`).

### Images in database (Phase 10)

See [Images (SQLite BLOBs — Phase 10)](#images-sqlite-blobs--phase-10) above.

---

## Post-MVP endpoints — reference (Phases 11A–13 implemented on `main`)

Contracts below match **shipped** behavior unless a bullet explicitly marks a gap (e.g. wizard UI vs API).

### Inventory part modal (Phase 11A)

**`POST /owned-sets/{owned_set_id}/set-parts`** — *implemented*; response extended:

```json
{
  "instance_line_id": 100,
  "part_id": 42,
  "catalog_line_id": 9001,
  "quantity": 2,
  "quantity_missing": 0
}
```

- Body unchanged: `part_num`, optional `part_name`, `color_id`, `color_name`, `quantity`.
- Client may call `PUT /parts/{part_id}/image` after **201** when the user selected a file.
- **`409`** if the part/color line already exists **on this copy**.

**`PATCH /owned-sets/{owned_set_id}/set-parts/{instance_line_id}`**

```json
{
  "part_name": "Plate 1 x 1",
  "color_id": 0,
  "color_name": "Black",
  "quantity": 4
}
```

- Updates shared catalog part name, catalog line color (may recreate line if color key changes — see implementation), and **this copy’s** `quantity`.
- **`part_num` not accepted** (read-only in UI).
- **`404`** if the line does not belong to this **`owned_sets` row** (this copy).

**`DELETE /owned-sets/{owned_set_id}/set-parts/{instance_line_id}`** → **`204`**

- Removes `owned_set_inventory_lines` for **this copy**.
- Deletes `set_part_inventory_lines` when **no copy** references that catalog line.
- Catalog-set cleanup when **last copy** deleted follows existing `DELETE /owned-sets/{id}` rules.

**`PATCH .../inventory-lines/{instance_line_id}`** (Phase 9, implemented) remains for inline **missing quantity** (and optional quantity) on the detail table; the part modal uses set-parts PATCH for full line edits.

### Part aliases (Phase 11B)

**`PATCH /api/parts/{part_id}/aliases`**

Request:

```json
{ "aliases": ["3024b", "3024pr"] }
```

Response **`200`:**

```json
{
  "part_id": 42,
  "part_num": "3024",
  "aliases": ["3024b", "3024pr"]
}
```

- **Replace-list** semantics: body is the full set of *other* identifiers for this part (exclude own `part_num` from chips in UI).
- Server enforces **symmetric closure** across the equivalence class (see [product-requirements.md §11.5](./product-requirements.md#115-part-aliases-bidirectional)).
- Manual rows use `source='user'`. If an alias string matches another existing `parts.part_num`, **merge** equivalence classes (simpler UX; no `409` unless validation fails).
- **`404`** unknown `part_id`; **`422`** invalid alias (empty, over max count e.g. 20).

### CSV import with Rebrickable (Phase 12)

**`POST /imports/csv`** response extended (example):

```json
{
  "instances_created": 3,
  "sets_fetched": 3,
  "existing_sets_skipped": 0,
  "skipped_existing_sets": [],
  "sets_failed": [
    { "token_index": 2, "set_num": "0000-1", "message": "HTTP 404 from Rebrickable" }
  ],
  "errors": [],
  "set_images_downloaded": 2,
  "minifig_images_downloaded": 3,
  "part_images_downloaded": 48,
  "image_downloads_failed": []
}
```

- Requires `REBRICKABLE_API_KEY`; **`400`** if missing.
- Per token: new catalog sets upsert catalog + template inventory + create **`owned_sets` row** + copy per-copy inventory (Phase 9), then download set, minifigure, and all inventory part images from Rebrickable CDN URLs into SQLite BLOBs. Existing catalog sets are skipped by default (listed in `skipped_existing_sets`) or copied locally when `existing_set_mode=copy`.
- Response includes `set_images_downloaded`, `minifig_images_downloaded`, `part_images_downloaded`, and `image_downloads_failed` (same shape as sync image counters).

### Manual add set (Phase 13)

**`GET /owned-sets/add-preview?set_num=…`** — **`200`**

Returns branching data for the **Add set** wizard (`AddSetWizard`) and for API clients.

| Field | Meaning |
|-------|--------|
| `set_num` | Normalized trimmed set number. |
| `catalog_exists` | `true` if a `catalog_sets` row already exists for this number. |
| `set_name`, `theme_name`, `year`, `num_parts`, `age`, `image_url` | Populated when **`catalog_exists`** (shared catalog + first non-null `owned_sets.age` among **copies** for age). |
| `existing_copy_count` | Number of `owned_sets` for that catalog set. |
| `suggested_label` | e.g. `Copy #n` for the next copy. |
| `set_parts` | Template set-part lines (`part_num`, `part_name`, `color_name`, `quantity`) when catalog exists; empty when `catalog_exists` is false. |

**`POST /owned-sets`** — create catalog + **first physical copy** **or** **add another copy** only (`owned_sets`).

| Case | Body | Server |
|------|------|--------|
| **Catalog exists** | **`set_num`** and optional **`label`** only. Sending `catalog` or `parts` → **400** (“omit catalog and parts”). | New `owned_sets` row; **`clone_instance_inventory`** from template. |
| **New catalog** | **`set_num`**; optional **`label`**, **`age`**, **`catalog`** (`name`, `theme_name`, `year`, `num_parts`), **`parts`** (array of `part_num`, optional `part_name`/`color_id`/`color_name`, `quantity` > 0). | Creates **`source=user`** catalog, optional lines from `parts`, **first copy**. |

**`GET /owned-sets/add-rebrickable-draft?set_num=…`** — **`200`** (live Rebrickable; **requires** `REBRICKABLE_API_KEY`)

Read-only wizard **prefill**: returns **`catalog`** (same shape as `POST` **`catalog`** input), **`age`**, **`parts`** (**non‑spare, non‑alternate** set‑part lines only; same row shape as `POST` **`parts`**), plus explanatory **`note`** (minifig BOM is excluded; use CSV/sync for full BOM). **`409`** if this **`set_num`** already exists locally (use **`add-preview`** + duplicate flow). **`400`** missing API key. **`502`** upstream Rebrickable failure (friendly message when **`404`** from API).

The **wizard** calls **`add-preview`** → step 2, then **`add-rebrickable-draft`** (optional) + **`POST`**. Rows with empty **`part_num`** are omitted from **`POST`**.

**Example — new copy only**

```json
{ "set_num": "6024-1", "label": "Copy #2" }
```

**Example — first row for a brand-new `set_num` (API client)**

```json
{
  "set_num": "99999-1",
  "catalog": { "name": "…", "theme_name": "…", "year": 2020, "num_parts": 100 },
  "parts": [{ "part_num": "3024", "color_id": 0, "quantity": 2 }]
}
```

Part alias editing: [Part aliases (Phase 11B)](#part-aliases-phase-11b) (not part of the wizard contract).

See also [Rebrickable sync — UI (jobs) and legacy synchronous route](#rebrickable-sync--ui-jobs-and-legacy-synchronous-route) for Import **Sync entire collection**, set detail scoped sync, optional `owned_set_ids`, and image download options.

## Reports

Read-only collection aggregates. Counts refer to **set copies** (`owned_sets`), not distinct catalog set numbers.

### Summary — Phase 15

**`GET /reports/summary`**

**Response `200`:**

```json
{
  "total_sets": 12,
  "investigated_sets": 8,
  "complete_sets": 5,
  "total_parts": 4200,
  "missing_parts": 37
}
```

| Field | Meaning |
|-------|---------|
| `total_sets` | All set copies in the collection |
| `investigated_sets` | Copies with `investigated = true` |
| `complete_sets` | Investigated copies with no inventory line where `quantity_missing > 0` |
| `total_parts` | Sum of `quantity` on all `owned_set_inventory_lines` (set parts and minifig BOM) |
| `missing_parts` | Sum of `quantity_missing` on all `owned_set_inventory_lines` |

### Incomplete sets — Phase 16

**`GET /reports/incomplete-sets?limit=50&offset=0`**

Paginated list of set copies with at least one inventory line where `quantity_missing > 0`.

**Response `200`:**

```json
{
  "items": [
    {
      "id": 1,
      "set_num": 6024,
      "name": "Police Car",
      "display_label": "Copy #1",
      "investigated": false,
      "missing_line_count": 1,
      "missing_parts_total": 2,
      "missing_lines": [
        {
          "part_id": 10,
          "part_num": "3001",
          "part_name": "Brick 2x4",
          "color_id": 0,
          "color_name": "Black",
          "quantity_missing": 2,
          "element_ids": ["300100"],
          "part_image_url": "/api/parts/10/image"
        }
      ]
    }
  ],
  "total": 1
}
```

| Field | Meaning |
|-------|---------|
| `missing_line_count` | Distinct inventory lines with `quantity_missing > 0` for this copy |
| `missing_parts_total` | Sum of `quantity_missing` for this copy |
| `missing_lines` | Only lines with `quantity_missing > 0` (set parts and minifig BOM) |

### Missing parts — Phase 17

**`GET /reports/missing-parts?owned_set_ids=1&owned_set_ids=2&limit=50&offset=0`**

Part-centric aggregation grouped by **`part_id` + color**. Omit `owned_set_ids` to include all incomplete copies; pass one or more ids to restrict the report to those set copies (ids without missing parts are ignored).

**Response `200`:**

```json
{
  "items": [
    {
      "part_id": 10,
      "part_num": "3001",
      "part_name": "Brick 2x4",
      "color_id": 0,
      "color_name": "Black",
      "quantity_missing_total": 5,
      "element_ids": ["300100"],
      "part_image_url": "/api/elements/300100/image",
      "needed_sets": [
        {
          "owned_set_id": 1,
          "set_num": 6024,
          "set_name": "Police Car",
          "display_label": "Copy #1",
          "quantity_missing": 2
        }
      ]
    }
  ],
  "total": 42
}
```

| Field | Meaning |
|-------|---------|
| `quantity_missing_total` | Sum of `quantity_missing` for this part+color across filtered copies |
| `needed_sets` | Each copy that still needs this part, with per-copy missing quantity |

**Export:** the missing-parts report page offers **Export PDF** (client-side). The UI fetches all report rows (paginated API requests with `limit=200`) for the active filter, then downloads a landscape PDF table with an **Image** column (same-origin `/api/elements/...` or `/api/parts/...` URLs only), plus Part, Color, Element ID, Needed, and **Sets** (set numbers only, optional `×qty`). The web UI **Sets** column uses `set_num`, catalog **`set_name`**, and copy **`display_label`** in link text.

## CORS

Backend allows the Vite dev origin (e.g. `http://localhost:5173`) via environment-driven CORS settings for MVP.

## OpenAPI

FastAPI auto-generates **OpenAPI** at `/openapi.json`; this document remains the **human rationale**; drift should be avoided by treating these specs as acceptance references during implementation.

## Related documents

- [README.md](./README.md) — index of all specification files in `docs/`
- [ci.md](./ci.md)
- [product-requirements.md](./product-requirements.md)
- [database-schema.md](./database-schema.md)
- [data-sources.md](./data-sources.md)
