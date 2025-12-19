# Barnacle MVP Contracts

This document defines the stable “contracts” between the three MVP layers:

- **IIIF models** (`barnacle_iiif.v2`)
- **ATR engines** (`barnacle_atr`)
- **Pipeline** (`barnacle_pipeline`)

The goal is to let each layer evolve independently while keeping interfaces stable.

---

## 1. IIIF traversal contract (Presentation 2.1)

### 1.1 Inputs
- A IIIF Presentation 2.1 **Manifest URI** (HTTP(S)).
- Optional: a local manifest JSON file path.

### 1.2 Core data contract

#### `Manifest` must provide
- **Identity**
  - `id: str` (from `@id`)
  - `type: Literal["sc:Manifest"]`
- **Label**
  - `label: str | dict | list` (raw)
  - `best_label() -> str`
- **Metadata**
  - `metadata: list[MetadataEntry] | None`
- **Sequences**
  - `sequences: list[Sequence]`
- **Traversal helper**
  - `canvases() -> Iterable[Canvas]`

#### `Canvas` must provide
- `id: str`
- `label: str | dict | list | None`
- `width: int | None`, `height: int | None`
- `images: list[Annotation]`
- Optional: `rendering`

#### `Annotation` must provide
- `resource: ImageResource`
- `on: str | None`

#### `ImageResource` must provide
- `service: ImageService | list[ImageService] | None`
- `width: int | None`, `height: int | None`
- `format: str | None`

#### `ImageService` must provide
- `id: str`
- `profile`
- `context`

### 1.3 Image URL resolution

- `Canvas.primary_image_service() -> ImageService | None`
- `Canvas.image_request_url(...) -> str`

Default request:
```
{service_id}/full/full/0/default.jpg
```

### 1.4 I/O

- `load_manifest(uri: str) -> Manifest`
- `dump_manifest(manifest: Manifest, path: Path) -> None`

---

## 2. ATR engine contract

### 2.1 `ATREngine`

```
recognize(image: ImageInput, *, context: ATRContext | None) -> ATRResult
```

### 2.2 `ImageInput`
- `Path`
- `URL`
- `bytes`
- `BinaryIO`

### 2.3 `ATRContext`
Optional metadata:
- manifest URI
- canvas ID
- page index
- cache key
- language hint

### 2.4 `ATRResult`
Required:
- `text: str`
- `engine: str`

Optional:
- `engine_version`
- `model_id`
- `models`
- `elapsed_ms`
- `warnings`
- `data` (structured OCR output)

---

## 3. Kraken engine contract

### 3.1 ModelRef

A recognition model may be specified by:
- DOI (Zenodo)
- installed model name
- filesystem path

### 3.2 `KrakenConfig`
- `model: ModelRef | None`
- `models: dict[str, ModelRef] | None`
- `multi_model: bool`
- `model_auto_install: bool = True`
- `cache_dir: Path | None`
- `return_structure: bool = False`

Exactly one of `model` or `models` must be set.

### 3.3 Model resolution
If a DOI is supplied and the model is not installed:
- run `kraken get <doi>`
- resolve installed model name/path
- record DOI + resolved name for reproducibility

---

## 4. Pipeline contract

### 4.1 Input
CSV rows with:
- `source_metadata_id`
- `ark`
- `manifest_url`

### 4.2 Per-page workflow
1. Resolve image URL from canvas
2. Run `ATREngine.recognize`
3. Append output record immediately

### 4.3 Output (JSONL)
Each line represents one page:

Required:
- manifest_url
- ark
- source_metadata_id
- canvas_id
- page_index
- image_url
- engine
- engine_config
- text

Optional:
- page_label
- elapsed_ms
- warnings
- errors
- data

### 4.4 Resume behavior
A page is “done” if:
- a record exists for `(manifest_url, canvas_id, engine_config)`

---

## 5. MVP invariants

- Stable IIIF traversal helpers
- Stable ATR engine interface
- Explicit, reproducible engine configuration
- Corpus-friendly outputs

---

*Checkpoint document generated for project handoff and continuation.*
