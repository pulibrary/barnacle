"""
Output path resolution and resume tracking.

Handles generation of output paths using SHA1 hashing for per-manifest files,
and tracks which pages have already been processed for resume functionality.
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
from typing import Any


def manifest_output_path(manifest_id: str, output_dir: Path) -> Path:
    """
    Generate SHA1-based output path for manifest.

    Creates a deterministic filename from the manifest URL using SHA1 hash.
    This ensures each manifest writes to its own file.

    Parameters:
        manifest_id: Manifest URL or identifier
        output_dir: Base directory for output files

    Returns:
        Path to output JSONL file

    Example:
        >>> output_dir = Path("runs/ocr")
        >>> manifest_id = "https://example.org/manifest"
        >>> path = manifest_output_path(manifest_id, output_dir)
        >>> print(path)
        runs/ocr/abc123...def.jsonl
    """
    sha1_hash = hashlib.sha1(manifest_id.encode("utf-8")).hexdigest()
    return output_dir / f"{sha1_hash}.jsonl"


def page_key(
    *,
    manifest_id: str,
    canvas_id: str,
    model: str,
    fmt: str,
    size: str,
    quality: str,
    region: str,
    rotation: str,
) -> str:
    """
    Generate stable identifier for a single OCR result.

    Creates a unique key for each page that incorporates all processing
    parameters. Used for resume-safe runs to identify already-processed pages.

    Parameters:
        manifest_id: Manifest URL
        canvas_id: Canvas identifier
        model: OCR model identifier
        fmt: IIIF image format
        size: IIIF size parameter
        quality: IIIF quality parameter
        region: IIIF region parameter
        rotation: IIIF rotation parameter

    Returns:
        Pipe-separated page key string

    Example:
        >>> key = page_key(
        ...     manifest_id="https://example.org/manifest",
        ...     canvas_id="https://example.org/canvas/1",
        ...     model="kraken_model",
        ...     fmt="jpg",
        ...     size="!3000,3000",
        ...     quality="default",
        ...     region="full",
        ...     rotation="0"
        ... )
    """
    return "|".join(
        [manifest_id, canvas_id, model, fmt, size, quality, region, rotation]
    )


def load_processed_keys(output_path: Path) -> set[str]:
    """
    Load page_key set from existing JSONL output file.

    Reads an existing output file and extracts all page_key values to
    determine which pages have already been processed. This enables
    resume functionality.

    Parameters:
        output_path: Path to JSONL output file

    Returns:
        Set of page_key strings that have been processed

    Example:
        >>> output_path = Path("runs/ocr/abc123.jsonl")
        >>> processed = load_processed_keys(output_path)
        >>> print(f"Already processed: {len(processed)} pages")
    """
    processed: set[str] = set()
    if not output_path.exists():
        return processed

    try:
        with output_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    # Ignore truncated/invalid lines (e.g., partial last line)
                    continue
                k = rec.get("page_key")
                if isinstance(k, str):
                    processed.add(k)
    except OSError:
        # If the file cannot be read, fall back to reprocessing
        return set()

    return processed


def append_record(output_path: Path, record: dict[str, Any]) -> None:
    """
    Append a record to JSONL output file.

    Writes a single JSON record as one line to the output file.
    Creates parent directories if they don't exist.

    Parameters:
        output_path: Path to JSONL output file
        record: Dictionary to write as JSON

    Example:
        >>> output_path = Path("runs/ocr/output.jsonl")
        >>> record = {"manifest_url": "...", "text": "..."}
        >>> append_record(output_path, record)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
