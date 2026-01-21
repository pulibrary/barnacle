"""
Single manifest processing worker.

Core processing function for OCR'ing a single manifest. Designed to be called
from SLURM job array tasks or other parallel execution environments.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import time
from datetime import datetime, timezone

import httpx

from barnacle.iiif.v2 import load_manifest, validate_manifest, ValidationIssue
from barnacle.ocr import KrakenBackend

from .output import page_key, load_processed_keys, append_record


DEFAULT_IIIF_SIZE = "!3000,3000"
DEFAULT_IIIF_FORMAT = "jpg"
DEFAULT_IIIF_QUALITY = "default"
DEFAULT_IIIF_REGION = "full"
DEFAULT_IIIF_ROTATION = "0"


@dataclass
class ProcessingResult:
    """
    Result of processing a single manifest.

    Attributes:
        manifest_id: Manifest URL
        pages_processed: Number of pages successfully processed
        pages_skipped: Number of pages skipped (resume)
        pages_failed: Number of pages that failed
        validation_issues: List of validation issues (if any)
        elapsed_seconds: Total processing time
        success: Whether processing completed successfully
    """

    manifest_id: str
    pages_processed: int
    pages_skipped: int
    pages_failed: int
    validation_issues: list[ValidationIssue]
    elapsed_seconds: float
    success: bool


def fetch_bytes(url: str, *, timeout: float = 30.0) -> bytes:
    """
    Fetch image bytes from URL.

    Parameters:
        url: Image URL
        timeout: Request timeout in seconds

    Returns:
        Image data as bytes

    Raises:
        httpx.HTTPError: If request fails
    """
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


def process_manifest(
    manifest_id: str,
    output_path: Path,
    *,
    model: str,
    cache_dir: Path,
    max_pages: int | None = None,
    resume: bool = True,
    model_auto_install: bool = True,
    size: str = DEFAULT_IIIF_SIZE,
    fmt: str = DEFAULT_IIIF_FORMAT,
    quality: str = DEFAULT_IIIF_QUALITY,
    region: str = DEFAULT_IIIF_REGION,
    rotation: str = DEFAULT_IIIF_ROTATION,
    source_metadata_id: str | None = None,
    ark: str | None = None,
) -> ProcessingResult:
    """
    Process single manifest: fetch, validate, OCR pages, write JSONL.

    This is the core worker function designed for SLURM job array execution.
    It handles all aspects of processing one manifest:
    - Fetching and validating the manifest
    - Iterating through canvases/pages
    - Downloading images (with caching)
    - Running OCR
    - Writing results incrementally
    - Resume from interruptions

    Parameters:
        manifest_id: Manifest URL or path
        output_path: Path to output JSONL file
        model: Kraken model reference (DOI, name, or path)
        cache_dir: Directory for image cache
        max_pages: Optional limit on number of pages to process
        resume: Skip pages already in output file
        model_auto_install: Auto-install model from DOI if needed
        size: IIIF size parameter
        fmt: IIIF image format
        quality: IIIF quality parameter
        region: IIIF region parameter
        rotation: IIIF rotation parameter
        source_metadata_id: Optional provenance field
        ark: Optional provenance field

    Returns:
        ProcessingResult with statistics

    Example:
        >>> result = process_manifest(
        ...     manifest_id="https://example.org/manifest",
        ...     output_path=Path("runs/ocr/abc123.jsonl"),
        ...     model="models/model.mlmodel",
        ...     cache_dir=Path("cache"),
        ... )
        >>> print(f"Processed {result.pages_processed} pages")
    """
    start_time = time.perf_counter()
    pages_processed = 0
    pages_skipped = 0
    pages_failed = 0

    # Initialize OCR backend
    backend = KrakenBackend(model_auto_install=model_auto_install)
    resolved_model = backend.resolve_model(model)

    # Setup cache directory
    img_cache = cache_dir / "images"
    img_cache.mkdir(parents=True, exist_ok=True)

    # Load resume state
    processed_keys = load_processed_keys(output_path) if resume else set()

    try:
        # Load and validate manifest
        manifest = load_manifest(manifest_id)
        validation_issues = validate_manifest(manifest)

        if validation_issues:
            # Manifest has validation issues, return early
            elapsed = time.perf_counter() - start_time
            return ProcessingResult(
                manifest_id=manifest_id,
                pages_processed=0,
                pages_skipped=0,
                pages_failed=0,
                validation_issues=validation_issues,
                elapsed_seconds=elapsed,
                success=False,
            )

        # Process each canvas/page
        for c_i, canvas in enumerate(manifest.canvases()):
            if max_pages is not None and pages_processed >= max_pages:
                break

            # Generate IIIF Image API URL
            image_url = canvas.image_url(
                region=region,
                size=size,
                rotation=rotation,
                quality=quality,
                fmt=fmt,
            )

            if image_url is None:
                pages_failed += 1
                continue

            canvas_id = canvas.id

            # Check if already processed (resume)
            k = page_key(
                manifest_id=manifest_id,
                canvas_id=canvas_id,
                model=resolved_model,
                fmt=fmt,
                size=size,
                quality=quality,
                region=region,
                rotation=rotation,
            )

            if resume and k in processed_keys:
                pages_skipped += 1
                continue

            # Download image (with caching)
            import hashlib

            cache_key = hashlib.sha1(image_url.encode("utf-8")).hexdigest()
            img_path = img_cache / f"{cache_key}.{fmt}"

            if not img_path.exists():
                try:
                    img_bytes = fetch_bytes(image_url)
                    img_path.write_bytes(img_bytes)
                except httpx.HTTPError:
                    pages_failed += 1
                    continue

            # Run OCR
            t0 = time.perf_counter()
            try:
                text_out = backend.ocr_image(img_path, model=resolved_model)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
            except Exception:
                pages_failed += 1
                continue

            # Write result
            rec: dict[str, Any] = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "page_key": k,
                "canvas_index": c_i,
                "engine": backend.name,
                "model": {"ref": model, "resolved": resolved_model},
                "manifest_url": manifest_id,
                "canvas_id": canvas_id,
                "image_url": image_url,
                "elapsed_ms": elapsed_ms,
                "text": text_out,
                "source_metadata_id": source_metadata_id,
                "ark": ark,
            }

            append_record(output_path, rec)
            if resume:
                processed_keys.add(k)
            pages_processed += 1

        elapsed = time.perf_counter() - start_time
        return ProcessingResult(
            manifest_id=manifest_id,
            pages_processed=pages_processed,
            pages_skipped=pages_skipped,
            pages_failed=pages_failed,
            validation_issues=[],
            elapsed_seconds=elapsed,
            success=True,
        )

    except Exception as e:
        elapsed = time.perf_counter() - start_time
        return ProcessingResult(
            manifest_id=manifest_id,
            pages_processed=pages_processed,
            pages_skipped=pages_skipped,
            pages_failed=pages_failed,
            validation_issues=[],
            elapsed_seconds=elapsed,
            success=False,
        )
