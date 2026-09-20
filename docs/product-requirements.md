# Product requirements — LEGO Collection Manager (MVP)

## Problem and goal

Collectors need a **local-first** way to record **their LEGO collection** (including **multiple physical copies** of the same set number), pull authoritative inventory data from documented online sources, and browse that data offline while tracking **missing parts per copy** and whether each copy has been **investigated** after purchase (common for second-hand sets). The MVP delivers a small web application backed by **SQLite**, with collection growth via **repeatable CSV imports**, **making a copy** when another physical purchase arrives, and catalog enrichment via the **Rebrickable API**.

## Target user

A single user running the app on their own machine (no multi-tenant accounts in MVP), often acquiring **second-hand** sets that may be incomplete until manually checked against the imported inventory.

## Engineering norms (repository)

**Stack, importer constraints, and automated-testing policy** are defined in the repository [project rules](../.cursor/rules/project-rules.mdc) (Cursor applies them across the tree). **How to run** the backend and frontend locally is in the root [`README.md`](../README.md).

**Product-level constraints (MVP):**

- **Single user** on one machine; no multi-tenant accounts (see [Non-goals](#non-goals-mvp)).
- **Local-first** persistence in SQLite; configurable `DATABASE_URL` (see [database-schema.md](./database-schema.md)).
- **Secrets:** API keys only via environment variables; document required variables in `backend/.env.example`; never commit real keys.
- **User media:** part, set, and minifigure photos are stored as **SQLite BLOBs** so reports and browsing work **offline** after upload or sync (see [database-schema.md](./database-schema.md) and [api-design.md](./api-design.md)).

## Domain glossary

Everything the app stores on disk is **in your collection**. There is **no** separate wishlist or LEGO catalog the user does not own. The **`catalog_sets`** table is an internal **shared slice** (metadata + inventory template) for a LEGO `set_num`, and it exists only while you have at least one **physical copy** in **`owned_sets`**. Deleting your **last copy** of that `set_num` removes the shared catalog rows for it as well.

| Term | Definition |
|------|------------|
| **Shared catalog (`catalog_sets`)** | Internal row for one LEGO `set_num`: name, theme, Rebrickable-derived inventory template, etc. **Not** “sets you don’t own” — it disappears when you delete your last copy. |
| **Set copy** | One physical copy of a LEGO set in **your** collection (row in **`owned_sets`**). The same `set_num` may appear as many copies (investigated or not, missing parts or not). REST path `/owned-sets` is this resource. |
| **Investigated** | A boolean on **each copy**: the user has manually checked that copy against its inventory (common for second-hand buys). |
| **Copy label** | Optional text on **a set copy** to distinguish copies sharing the same `set_num`. When unset, the UI displays **`Copy #n`** where `n` is the copy index (1-based among copies, oldest first). |
| **Recommended age (years)** | Integer on each **set copy** (`owned_sets.age`, shared across copies of the same `set_num`). Parsed from Rebrickable `age_range` when present; **often omitted** by the API — user fills it on detail. Shown as `?` when unset. Editing age on one copy updates **all** copies sharing that `set_num`. |
| **Part** | A LEGO element type identified primarily by a part number; may have **aliases** (alternate identifiers). |
| **Color** | A color identifier and display name as provided by the importer (used on inventory lines). |
| **Set inventory line** | A row linking a catalog set to a part in a given color with quantity and optional image URL. Rebrickable spare and alternate rows are ignored on import. **Stickered** and **plain** variants are distinct lines when the source uses distinct part identities. |
| **Minifigure (catalog)** | A minifig design referenced by the source (e.g. `fig-…`); may appear as its own inventory line on a set and may have **constituent part** lines when the API exposes a minifig BOM. |
| **Missing item** | User-tracked gap for a specific **set copy**: which part (and color) is missing, in what quantity, and optionally **one user-provided photo** stored locally for offline reference and future reports. |

## MVP scope

### 1. CSV import of LEGO set numbers

**User outcome:** The user uploads a simple text file listing set numbers (comma-separated, no header). Each import **adds** **new copies** (`owned_sets`) so they can record newly acquired sets at any time.

**Acceptance criteria:**

- File format matches [data-sources.md](./data-sources.md): **UTF-8**, **no header row**, **no columns** — only Rebrickable-compatible **set numbers** separated by commas (whitespace and newlines around tokens are ignored).
- **Each token** in the file creates **one new** `owned_sets` row, even when the same `set_num` appears multiple times in the file or already exists in the collection (multiple physical copies).
- Malformed tokens (empty after trim, invalid characters per parser rules) are reported as **token-level errors**; valid tokens still process when partial success is supported (documented in API).
- Import is **additive**: it does not delete or replace existing copies. Re-uploading the same file creates **additional** copies (user responsibility).
- Response summarizes **copies created** (JSON may still say `instances_created`), stub catalog rows created, and errors.

### 2. Rebrickable API import

**User outcome:** For **sets already in the collection** (and their shared catalog metadata and inventories), the app can fetch or refresh data from Rebrickable using an API key from the environment.

**Acceptance criteria:**

- Import requires `REBRICKABLE_API_KEY` (or the name agreed in [data-sources.md](./data-sources.md)); clear error if missing.
- Successful sync creates or updates **catalog** data (sets, parts, colors, inventory lines, minifigs as defined in [database-schema.md](./database-schema.md)).
- Each imported entity carries **source metadata** (at minimum: source name, external identifiers, last fetch timestamp).
- Re-running sync for the same **physical copies** **updates** shared catalog rows and inventory for the underlying `set_num`; does not duplicate primary catalog entities.
- Failures from the API (network, 4xx/5xx) surface as actionable errors without corrupting existing rows (transaction boundaries described in [api-design.md](./api-design.md)).

### 2b. Import from another database file

**User outcome:** The user can merge catalog and collection data from a second LEGO Collection Manager SQLite `.db` file (for example another machine or an older backup) without using Rebrickable.

**Acceptance criteria:**

- **Import** page (Edit mode) accepts a `.db` upload and a mode: **add only new sets** or **add new sets and update existing** (see [api-design.md](./api-design.md)).
- Sets are matched by catalog **`(set_number, set_variant)`**; invalid or non-app databases return **`400`**.
- **Add only new:** imports sets (and related catalog/inventory/images) not already present; skips existing set numbers.
- **Add and update:** refreshes catalog metadata, images, and inventory for existing sets while **preserving** per-copy **age** (when already set), **theme** (when catalog already has a theme), **copy labels**, and **missing** quantities/items.
- No live network calls; tests use in-memory or temp-file SQLite fixtures.

### 3. SQLite storage

**User outcome:** All collection and catalog data persist in a single local SQLite database file; user-uploaded part and set images persist in the same database (Phase 10 BLOB columns).

**Acceptance criteria:**

- Database path is configurable (environment variable); sensible default for local dev documented in [development-plan.md](./development-plan.md).
- Schema is versioned with **Alembic** migrations.
- Application starts only if migrations can be applied or the database is at the expected revision.

### 4. Sets list

**User outcome:** A screen lists **every physical copy** in the collection with enough context to distinguish duplicates of the same `set_num` (set number, name, year, thumbnail, investigation status, missing count, optional label).

**Acceptance criteria:**

- List is **paginated** (offset/limit) per [api-design.md](./api-design.md).
- Rows link to the **set detail** view for that copy’s `id`.
- **Investigated** vs **not investigated** is visible (badge or column); optional filter by investigation state.
- **Theme** multi-select filter and **Missing parts only** toggle; list preferences (investigation filter, theme filter, missing-only, sort field/direction, group-by) persist in **`localStorage`** key `lcm.setsListPreferences` across navigation and refresh.
- After a successful theme rename on set detail, the active theme filter stays in sync when the user returns to the list: **`scope: all`** replaces the old theme name with the new; **`scope: this_set`** keeps the old theme and adds the new one (queued in **`sessionStorage`** key `lcm.pendingThemeFilterSync`, consumed on list mount/navigation).
- Multiple rows may share the same `set_num` (distinct `id`).
- Sets without a successful catalog sync yet may show **placeholder or partial** metadata until sync completes.
- Each row shows **`{display_label} — {set_num}`** where `display_label` is the user label or default `Copy #n`.
- Under the set number line, show **name** (default “Unknown name”), **theme** (default “Unknown theme”), **part count** (default `?`), and **age** (default `?`).
- **Make a copy** action per row opens a **confirmation dialog** before creating a new copy (see [§8](#8-duplicate-a-set-copy-make-a-copy)); no duplicate action on the detail page.

### 5. Set detail (one copy)

**User outcome:** Selecting **a copy** shows shared catalog metadata for its `set_num`, investigation controls, optional label, plus the full **parts inventory** (including colors, quantities, images where available). Minifigures appear consistently with how Rebrickable models them.

**Acceptance criteria:**

- Detail view includes theme, year, name, set number, and image when present.
- User can edit **per-copy fields**: `label` (default `Copy #n` when empty in the UI), `investigated`, `age`, and `notes`.
- User can **delete** **this copy** (with confirmation); missing rows for that copy are removed.
- **Make a copy** is **not** on the detail page (list only, with confirmation dialog per [§8](#8-duplicate-a-set-copy-make-a-copy)).
- User can edit **shared catalog fields** on detail (`name`, theme, part count, age, etc.); changes apply to **every copy** with the same `catalog_set_id`, except **`set_num`** (see below) and **theme** when the user chooses **Only this set** in the theme scope dialog (see below).
- When the user changes **theme** and more than one catalog set in the collection shares the current theme name, show **Update theme?** with **All sets with this theme**, **Only this set**, and **Cancel** (Cancel restores the previous theme value without saving).
- Changing **`set_num`**: show a warning (“You are about to change the LEGO set number”); **Cancel** restores the previous value; **Continue** re-links **only this copy** to the new set number (create or match `catalog_sets` row) without changing other copies.
- Inventory table supports sorting or stable default order (e.g. by part number, then color).
- Rebrickable **spare** and **alternate** inventory rows are **not imported** (not shown in the UI).
- Distinct **stickered vs plain** parts appear as distinct rows matching importer data.
- User can **add** a set-part via a modal (**+** control) in **Edit** mode; modal supports optional **part image** upload (Phase 11A).
- User can **open the part modal** by clicking a set-part row: in **Edit** mode the modal is **Edit part** (update/delete); in **View** and **Investigate** modes the modal is read-only **Part view** (title “Part view”, catalog fields disabled, single **OK** button). **Part view** and **Edit part** (existing lines) show **Element ID** (comma-separated from `element_ids`) as the first identifier field, not part number.
- Set-parts table shows **Element IDs** per line; user edits aliases in the **Edit part** modal only (Phase 11B).
- User can **click the set box image** or a **minifigure image** on set detail to view it enlarged (lightbox); click the image again or press **Escape** to close. In **Edit** mode (`canEditImages`), user can upload/replace/delete set and minifigure photos via the catalog image endpoints.

### 6. Search by set number and part number

**User outcome:** The user finds **set copies** or **parts** already in the collection by typing a set number or part number (or alias).

**Acceptance criteria:**

- Search returns **set copies** when matching set numbers (including normalized forms agreed in [data-sources.md](./data-sources.md)); results may include multiple rows for one `set_num`.
- Search returns **parts** that appear **in collection inventories** when matching part number or a stored **alias**.
- Empty query returns a **validation error** (400), not a full dump.
- Response time remains acceptable on a typical personal library (thousands of parts); indexes defined in [database-schema.md](./database-schema.md).

### 7. Missing part tracking

**User outcome:** From **one copy’s** inventory, the user marks parts (per color) as missing, adjusts quantities, clears them when found, and attaches **at most one local image** per missing line for offline reference and future reports.

**Acceptance criteria:**

- Missing state is stored **per physical copy**, not globally.
- User cannot mark missing more than the **expected quantity** from inventory for that part/color (validation).
- UI and API expose current missing lines and remaining “complete” status at a glance for **that copy**.
- Clearing missing removes or zeroes the corresponding records without deleting catalog inventory.
- User can **upload**, **replace**, and **remove** the photo for a missing line (API implemented; dedicated missing-photo UI is **deferred** — `canEditMissingPhotos` exists for future use); bytes are stored on the line’s primary **Element ID** in **`element_images`** when element IDs exist, otherwise on the **`parts`** record, and served via same-origin API URLs (no dependency on Rebrickable CDN for that photo).

### 8. Duplicate a set copy (“Make a copy”)

**User outcome:** When the user buys another copy of the same LEGO set number, they use **Make a copy** on the **sets list** to add another **physical copy** after confirming in a dialog.

**Acceptance criteria:**

- Button label is **Make a copy** (not “Add copy”).
- Action available from **sets list only** (not on set detail).
- Dialog states that a copy of set number **X** is being created; shows editable **label** prefilled with **`Copy #n`** (`n` = number of existing copies for that `set_num` + 1); **Cancel** and **Create a copy** buttons; POST runs only after confirm.
- Creates a new `owned_sets` row with the same `catalog_set_id` as the source row.
- New copy has `investigated` = **false**, confirmed `label`, `age` copied from source when set (else **null**), `notes` = **null**, and **no** `missing_items`.
- Response returns the new copy’s `id` for navigation.
- **`404`** if the source set copy **id** does not exist.
- Does not modify or delete the source copy.

### 9. Delete a set copy

**User outcome:** The user can remove **a physical copy** they no longer have (or no longer want tracked).

**Acceptance criteria:**

- **Delete** action on the **set detail** view (after opening that copy), with a confirmation dialog.
- **`DELETE /owned-sets/{id}`** removes the copy and its `missing_items`. Part/set BLOB images on shared catalog rows remain unless this was the **last copy** for that `set_num` (then shared catalog and inventory are deleted too).
- **`404`** if the id does not exist.

### 10. Shared vs per-copy catalog edits

| Field | Scope when edited from detail |
|-------|-------------------------------|
| `set_num` | **This copy only**, after warning + Continue; Cancel restores previous value. |
| `name`, `num_parts`, `age`, etc. | **All copies** sharing the same `catalog_set_id`. |
| `theme` | **All copies** sharing the same theme name when user chooses **All sets with this theme**; **this copy only** (re-link to separate theme row) when user chooses **Only this set**. |

**Provenance:** every field in the table above (and `set_num`) may be filled from **Rebrickable** (or left empty after CSV import) **or** entered/edited by the user on set detail—except **`label`**, which is user-only **per copy**. See [data-sources.md — Catalog metadata (dual source)](./data-sources.md#catalog-metadata-dual-source). Re-running Rebrickable sync refreshes safe source fields (set name, set image, part names/images, part counts, inventory lines, and per-copy part quantities) while preserving theme, year, age, investigated, missing, label, and notes.

Rebrickable may populate age when **`age_range`** appears on the set response (`6+` → store **`6`**). When Rebrickable has no age, the user enters it on the set detail form or uses the Import page’s local metadata update to fill missing ages from `data/age.csv` (`7+` → `7`). Successful sync/import **never clears** existing age solely because `age_range` is missing — only explicit user PATCH clears or changes age. CSV import does **not** rename existing copy labels; duplicate custom labels are allowed.

## 11. Post-MVP collection semantics (Phases 9–14)

The following extends MVP after Phase 8. See [development-plan.md](./development-plan.md) for delivery order and current **Phase 14** sync scope. **Phases 9–10** and core **11A, 11B, 12,** and **13** are implemented on **`main`**; **Phase 14** now includes bulk sync, current-set scoped sync, and optional image download controls.

### 11.1 Collection invariant (everything is your collection)

The database does not store LEGO sets outside what the user tracks in this app. Every `catalog_sets` row has at least one `owned_sets` row. Deleting the **last copy** for a `set_num` removes shared catalog and inventory for that number (existing delete rule).

### 11.2 Rebrickable fetch and image policy

When importing or enriching from Rebrickable (CSV import in Phase 12, optional prefill in manual add, and existing sync endpoint):

- **Fetch:** set metadata, full set parts inventory, minifigs, and minifig BOMs. **Age** is applied on first import only when Rebrickable exposes `age_range`; afterwards the user controls age on set detail.
- **CSV import:** after each successful Rebrickable catalog fetch per token, downloads set image BLOBs, minifigure image BLOBs, and **element-scoped** part image BLOBs for all inventory lines (including minifig BOM parts). Requires persisted element IDs from `elements.csv` enrichment for color-specific part thumbnails.
- **Manual prefill (Add set wizard):** does **not** fetch image bytes from Rebrickable CDN URLs.
- **Rebrickable sync:** may optionally download set image BLOBs, minifigure image BLOBs, and **element-scoped** part image BLOBs into SQLite when the user selects those options. Part image modes are **none**, **missing parts only**, or **all synced inventory parts**; both part modes include minifig BOM parts. Downloads use the line’s Rebrickable element URL and store bytes in **`element_images`** keyed by primary Element ID (requires persisted element IDs).

User-uploaded and sync-downloaded images are stored in SQLite (Phase 10). There are no local cache folders.

### 11.3 Shared vs per-copy fields

| Data | Scope when user edits |
|------|------------------------|
| Set name, theme, year, number of parts, age, **set image** | **All copies** sharing the same `catalog_set_id` / `set_num`. |
| **Minifigure image** | **Shared** per `catalog_minifigs` row (catalog-wide for that minifig identity). |
| Copy label, investigated, notes | **This copy only**. |
| `set_num` re-link | **This copy only** (with warning; existing MVP rule). |
| **Part quantity** on inventory | **This copy only** (Phase 9). |
| **Missing quantity** per line | **This copy only**; must satisfy `0 ≤ missing ≤ quantity` for that copy’s line. |
| **Element IDs** | **Global per part alias class + color** — see §11.5 and `part_color_keys` in [database-schema.md](./database-schema.md). All sets sharing the same colored part read the same Element ID list. |
| **Part image (display)** | **Shared per colored part** when Element IDs and element BLOBs exist (via `element_images`); otherwise **global per `parts` row** fallback. Part-modal uploads still target the global **`parts`** row. |
| **Part aliases** | **Symmetric equivalence class** — see §11.5. |

### 11.4 Part images

- Inventory lines **may** show a local image resolved from **`element_images`** (first matching Element ID on the line) or from the global **`parts`** BLOB as fallback.
- One BLOB per Element ID and one global BLOB per part (JPEG/PNG in DB, max 5 MB).
- **Add** and **edit** part modals in **Edit** mode include upload/replace/delete for the global part image on the **`parts`** row.
- **Part view** in **View** and **Investigate** is read-only for part photos (no upload). Both modes show the color-specific line **`image_url`** only.
- Removing a part photo clears **`parts.image_blob`** and sets **`part_image_user_removed`** (global part row only).
- Inventory list thumbnails, **Part view**, and **Edit part** preview use **`image_url`** (element BLOB first per line, then part BLOB fallback). **`part_image_url`** is exposed for the global part BLOB only; upload/replace/delete in **Edit part** still targets **`PUT /parts/{part_id}/image`**.
- Rebrickable sync with part-image download populates **`element_images`** for color-specific thumbnails.

### 11.5 Part aliases (bidirectional)

Users may edit the alias list for a part (Phase **11B** UI: chip list in **PartLineModal**). The system maintains an **undirected** alias group:

- If part **B** is added to part **X**’s alias list, **X** is added to **B**’s alias list.
- If part **A** is removed from **X**’s alias list, **X** is removed from **A**’s alias list.

Search treats all members of the group as interchangeable for part-number lookup.

### 11.6a Database merge import (offline `.db`)

- **Import** page section **Import from another database**; backend `POST /imports/database` and `database_import_service` (see [api-design.md](./api-design.md)).
- Modes and preservation rules match §2b above.

### 11.6 CSV import (Phase 12)

Unchanged additive semantics (one token → one new physical copy). Additionally, for each token the app calls Rebrickable and upserts **full** catalog inventory, then downloads set, minifigure, and part images when URLs are available. Failures are per-token; valid tokens still succeed.

### 11.7 Manual add set (Phase 13)

1. User enters **set number** (only required field).
2. If set number **already exists:** a **Cancel / Continue** warning states that a **new copy** will be created, filled from the **catalog part list in the database**, and that **missing items** and **investigated** status are **not** copied; **Continue** opens read-only catalog summary + optional template **parts** preview; user sets **label**; **submit** creates the copy (**two-step** wizard plus the existing-set warning).
3. If set number **is new:** user enters **shared catalog** metadata (name, theme, year, part count, optional **age**), **copy label**, optional **manual part rows**, and optional **Fetch from Rebrickable** (**`GET /owned-sets/add-rebrickable-draft`**; no image bytes)—which fills metadata and **set-level** inventory lines (**spares/alternates omitted**); minifigs and full BOM still come from **CSV** (§11.6), **sync** (Phase **14**), or later refinement. User **submits** to create **`source=user`** catalog + **first** copy. Omitting part rows yields an empty template; inventory can still be added via **PartLineModal** or **`POST /owned-sets`** with **`parts`**. (**Two-step** wizard; no standalone “confirm-only” third step.)

### 11.8 Part alias editing in modal (Phase 11B)

- **AliasChipEditor** in add and edit **PartLineModal**: removable chips plus “Add alias” field; canonical **part number** shown separately (read-only on edit), not as a chip.
- API: `PATCH /parts/{part_id}/aliases` with replace-list body; server enforces symmetric closure (§11.5).
- Alias edits are **global** for the equivalence class (like part images): all sets using any member part reflect the updated alias group in search and detail.

### 11.9 Sync UX (**Phase 14**)

- **Shipped:** **Import** and **set detail** run CSV import, database import, and Rebrickable sync via **`POST /api/imports/jobs`** (start → poll → cancel). Progress and cancel stay available while navigating the app (`ImportJobProvider`, optional banner link to Import). **`GET /api/imports/failed-sets.csv`** when catalog fetch failures were recorded. Legacy **`POST /imports/rebrickable/sync`** (and csv/database sync routes) remain for API clients and tests.
- **Preservation policy:** sync updates set/part names, set/part images, number of parts, catalog inventory, and per-copy part quantities. It does not update theme, year, age, investigated, missing quantities/items, labels, or notes.
- **Image options:** both sync surfaces default to **not** downloading set images (opt-in). Part image download defaults to **none**; users may download part images only for missing parts or for all synced inventory parts, including minifig BOM parts.
- **Local metadata update:** the Import page can fill missing age values and unknown themes from local CSV files without calling Rebrickable. It uses `data/age.csv` for age, and `data/sets.csv` plus `data/themes.csv` for theme, storing the parent theme when `parent_id` exists.
- **Backlog:** documented conflict policy vs manual/instance edits, and richer subset selection from list views — see [development-plan.md](./development-plan.md).

### 11.10 Settings and app modes (Phase 18)

**User outcome:** The user chooses how much of the app is editable without leaving the collection context.

**Acceptance criteria:**

- **Settings** page (`/settings`) with **View**, **Investigate**, and **Edit** modes; choice persists in browser **localStorage**; default is **View**.
- **View:** browse collection, search, and reports only — no sync, import, add/duplicate, or data edits; clicking a part row opens read-only **Part view**.
- **Investigate:** toggle **Investigated** and update **missing** quantities; clicking a part row opens read-only **Part view** (same image display as View); dedicated missing-line photo UI remains deferred.
- **Edit:** full app behavior (import, sync, catalog/copy edits, part CRUD, delete, images). Switching to Edit will require a **password** in a future release (stub hook in place).
- Header shows current mode label; **Add set** and **Import** nav entries are disabled outside Edit with a tooltip pointing to Settings.
- Mode gating is **UI-only** for MVP (API remains open for local single-user use).

**Capability flags** (frontend `getCapabilities()`): `canSync`, `canImport`, `canAddOrDuplicate`, `canEditCopyFields`, `canEditCatalog`, `canEditQuantities`, `canEditParts`, `canDeleteCopy`, `canEditImages`, `canToggleInvestigated`, `canEditMissing`, `canEditMissingPhotos` (reserved for deferred per-missing-line photo UI).

## UX surfaces (MVP)

1. **Sets list** — layout per [§4](#4-sets-list); **Make a copy** with confirmation dialog per row.
2. **Set detail** — per-copy fields + shared catalog fields + inventory + missing panel; **delete this copy**; no duplicate button.
3. **Search** — single entry point or dual mode (set vs part) per API design.
4. **Import** — CSV/text file upload (additive, Phase **12** enriches from Rebrickable); **Import from another database** (offline `.db` merge); **Sync entire collection** with image options (Phase **14**); **Add set** wizard (Phase **13** core); **PartLineModal** on set detail (Phases **11A–11B**).
5. **Reports** — collection summary (Phase **15**); incomplete sets with missing lines per copy (Phase **16**); missing-parts aggregation with optional set-copy filter, web **Sets** links showing catalog name, and **PDF export** with set numbers only in the Sets column (Phase **17**).
6. **Settings** — app mode (View / Investigate / Edit) per [§11.10](#1110-settings-and-app-modes-phase-18).

## Non-goals (MVP)

- Multi-user authentication, roles, or hosted SaaS deployment requirements.
- Cloud sync, backup, or merge across devices.
- BrickLink, BrickOwl, or other marketplaces; pricing or availability.
- Native mobile apps.
- **PDF/print export** for reports other than the missing-parts report (missing-parts PDF export is implemented on `/reports/missing`).
- Advanced analytics, wish lists, or part-out planning.

## Related documents

- [README.md](./README.md) — index of all specification files in `docs/`.
- [data-sources.md](./data-sources.md) — CSV and Rebrickable contracts.
- [database-schema.md](./database-schema.md) — tables and relationships.
- [api-design.md](./api-design.md) — REST endpoints and payloads.
- [development-plan.md](./development-plan.md) — delivery phases.
- [testing-strategy.md](./testing-strategy.md) — verification approach.
- [ci.md](./ci.md) — continuous integration (push/PR).
