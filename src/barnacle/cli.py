"""
Barnacle CLI

Commands:
- validate: Validate IIIF manifests/collections
- ocr: Run OCR on manifests/collections
- sample-image-url: Extract sample IIIF image URL
"""

from __future__ import annotations

from csv import DictReader
import json
from pathlib import Path
from typing import Any

import time
from datetime import datetime, timezone

import httpx
import typer
import logging

from barnacle.ocr import KrakenBackend, DEFAULT_MODEL
from barnacle.iiif.v2 import (
    load_manifest,
    load_json,
    parse_manifest,
    parse_collection,
    is_collection,
    is_manifest,
    iter_manifests,
    validate_manifest,
    validate_collection,
    validate_canvas,
)
from barnacle.pipeline.output import (
    page_key,
    load_processed_keys,
    append_record,
    manifest_output_path,
    run_report_path,
    read_jsonl_records,
)
from barnacle.pipeline.worker import process_manifest

app = typer.Typer(add_completion=False, help="Barnacle MVP tooling")

DEFAULT_IIIF_SIZE = "!3000,3000"  # long-side constraint; good OCR/throughput tradeoff
DEFAULT_IIIF_FORMAT = "jpg"
DEFAULT_IIIF_QUALITY = "default"
DEFAULT_IIIF_REGION = "full"
DEFAULT_IIIF_ROTATION = "0"

class JsonFormatter(logging.Formatter):
    """Simple JSON formatter for structured logs."""
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
            "logger": record.name,
        }
        # Include any custom attributes passed via `extra=`.
        reserved = {
            "name","msg","args","levelname","levelno","pathname","filename","module",
            "exc_info","exc_text","stack_info","lineno","funcName","created","msecs",
            "relativeCreated","thread","threadName","processName","process",
        }
        for k, v in record.__dict__.items():
            if k in reserved or k.startswith("_"):
                continue
            try:
                json.dumps(v)
                payload[k] = v
            except TypeError:
                payload[k] = repr(v)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str) -> logging.Logger:
    logger = logging.getLogger("barnacle")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.handlers[:] = [handler]
    logger.propagate = False
    return logger


LOGGER = logging.getLogger("barnacle")


def fetch_manifest(url: str) -> dict[str, Any]:
    """Fetch manifest from URL (backward compatibility helper)."""
    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()
def fetch_bytes(url: str, *, timeout: float = 30.0) -> bytes:
    """Fetch binary content from URL."""
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


@app.command("validate")
def validate_cmd(
    manifest_or_collection: str = typer.Argument(..., help="Manifest or Collection JSON path or URL"),
    skip_manifests: bool = typer.Option(
        False, "--skip-manifests", help="For collections, only validate collection structure (skip manifests)"
    ),
) -> None:
    """Validate a IIIF Presentation 2.x manifest or collection against pipeline requirements."""
    data = load_json(manifest_or_collection)
    all_issues = []

    # If root is a Collection, validate its structure first
    if is_collection(manifest_or_collection):
        collection = parse_collection(data)
        collection_issues = validate_collection(collection)
        if collection_issues:
            all_issues.append((manifest_or_collection, collection_issues))

        if skip_manifests:
            # Only validate collection structure, skip manifest fetching
            if all_issues:
                total_issues = sum(len(issues) for _, issues in all_issues)
                typer.echo(f"❌ Collection validation failed: {total_issues} issue(s)\n")
                for resource_id, issues in all_issues:
                    typer.echo(f"\nResource: {resource_id}")
                    for i, issue in enumerate(issues, start=1):
                        typer.echo(f"  {i:>3}. {issue.path}: {issue.message}")
                raise typer.Exit(code=2)
            else:
                typer.echo("✅ Collection validation passed (pipeline requirements).")
                return

    # Validate each manifest (works for both single manifests and collections)
    try:
        for manifest_id, manifest in iter_manifests(manifest_or_collection):
            issues = validate_manifest(manifest)
            if issues:
                all_issues.append((manifest_id, issues))
    except Exception as e:
        typer.echo(f"❌ Error processing manifests: {e}", err=True)
        raise typer.Exit(code=1)

    if all_issues:
        total_issues = sum(len(issues) for _, issues in all_issues)
        typer.echo(f"❌ Validation failed: {total_issues} issue(s) across {len(all_issues)} resource(s)\n")
        for resource_id, issues in all_issues:
            typer.echo(f"\nResource: {resource_id}")
            for i, issue in enumerate(issues, start=1):
                typer.echo(f"  {i:>3}. {issue.path}: {issue.message}")
        raise typer.Exit(code=2)

    typer.echo("✅ Validation passed (pipeline requirements).")

@app.command("validate_all")
def validate_all_cmd(
    path_to_csv_file: str = typer.Argument(..., help="Path to Figgy report"),
) -> None:
    """Validate a table of IIIF Presentation 2.x manifests against pipeline requirements."""
    with Path(path_to_csv_file).open('r') as csv_file:
        reader: DictReader = DictReader(csv_file)
        for row in reader:
            manifest_url: str = row['manifest_url']
            try:
                manifest = load_manifest(manifest_url)
            except httpx.HTTPError as e:
                typer.echo(f"❌ : Could not access manifest: {e}")
                continue

            issues = validate_manifest(manifest)
            if issues:
                typer.echo(f"❌ {manifest_url}: Validation failed ({len(issues)} issue(s))\n")
                for i, issue in enumerate(issues, start=1):
                    typer.echo(f"  {i:>3}. {issue.path}: {issue.message}")
            else:
                typer.echo(f"✅ {manifest_url}: Validation passed")


@app.command("run")
def run_cmd(
    manifest_list: Path = typer.Argument(..., help="File containing manifest URLs (one per line)"),
    output_dir: Path = typer.Argument(..., help="Output directory for JSONL files"),
    max_pages: int | None = typer.Option(None, "--max-pages", help="Limit pages per manifest (for testing)"),
    model: str | None = typer.Option(None, "--model", help="Override default Kraken model"),
    cache_dir: Path = typer.Option(
        Path(".barnacle-cache"), "--cache-dir", help="Cache directory for downloaded images"
    ),
    log_level: str = typer.Option("INFO", "--log-level", help="Log level"),
    clear_cache_after: bool = typer.Option(
        False,
        "--clear-cache-after/--keep-cache",
        help="Delete downloaded images after each manifest is successfully processed",
    ),
) -> None:
    """
    Run OCR on a list of manifests.

    Reads manifest URLs from MANIFEST_LIST (one per line) and writes
    JSONL output files to OUTPUT_DIR (one file per manifest, SHA1-named).

    Example:
        barnacle run manifests.txt output/ --max-pages 5
    """
    global LOGGER
    LOGGER = setup_logging(log_level)

    # Expand paths
    manifest_list = manifest_list.expanduser()
    output_dir = output_dir.expanduser()
    cache_dir = cache_dir.expanduser()

    # Validate manifest list file exists
    if not manifest_list.exists():
        typer.echo(f"Error: Manifest list file not found: {manifest_list}", err=True)
        raise typer.Exit(code=1)

    # Read manifest URLs from file
    manifest_urls = []
    with manifest_list.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                manifest_urls.append(line)

    if not manifest_urls:
        typer.echo("Error: No manifest URLs found in file", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(manifest_urls)} manifest(s) to process")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Use default model if not specified
    effective_model = model if model else DEFAULT_MODEL
    typer.echo(f"Using model: {effective_model}")

    # Process each manifest
    manifest_count = 0
    total_pages = 0
    skipped_manifests = 0
    failed_manifests = []

    for manifest_url in manifest_urls:
        manifest_count += 1

        # Generate output path using SHA1
        output_path = manifest_output_path(manifest_url, output_dir)

        # Skip if output file already exists (resume behavior)
        if output_path.exists():
            typer.echo(f"⏭️  [{manifest_count}/{len(manifest_urls)}] Skipping (already exists): {output_path.name}")
            skipped_manifests += 1
            continue

        typer.echo(f"\n📄 [{manifest_count}/{len(manifest_urls)}] Processing: {manifest_url}")

        # Process manifest
        result = process_manifest(
            manifest_id=manifest_url,
            output_path=output_path,
            model=effective_model,
            cache_dir=cache_dir,
            max_pages=max_pages,
            resume=True,
            clear_cache_after=clear_cache_after,
        )

        # Report results
        if result.validation_issues:
            typer.echo(
                f"⚠️  Validation issues ({len(result.validation_issues)}), but processing continued:",
                err=True
            )
            for issue in result.validation_issues[:5]:
                typer.echo(f"  - {issue.path}: {issue.message}", err=True)
            if len(result.validation_issues) > 5:
                typer.echo(f"  ... and {len(result.validation_issues) - 5} more", err=True)

        if result.success:
            total_pages += result.pages_processed
            typer.echo(
                f"✅ Completed: {result.pages_processed} pages processed, "
                f"{result.pages_skipped} skipped, "
                f"{result.pages_failed} failed "
                f"({result.elapsed_seconds:.1f}s)"
            )
            typer.echo(f"   Output: {output_path}")
        else:
            failed_manifests.append(manifest_url)
            typer.echo(f"❌ Failed to process manifest: {manifest_url}", err=True)
            typer.echo("  (Check log output above for error details)", err=True)

    # Final summary
    typer.echo(f"\n{'='*60}")
    typer.echo(f"📊 Summary:")
    typer.echo(f"  Manifests processed: {manifest_count - skipped_manifests - len(failed_manifests)}")
    typer.echo(f"  Manifests skipped (already exist): {skipped_manifests}")
    typer.echo(f"  Manifests failed: {len(failed_manifests)}")
    typer.echo(f"  Total pages: {total_pages}")
    typer.echo(f"  Output directory: {output_dir}")

    if failed_manifests:
        typer.echo(f"\n❌ Failed manifests ({len(failed_manifests)}):")
        for manifest_url in failed_manifests:
            typer.echo(f"  - {manifest_url}")
        raise typer.Exit(code=1)




@app.command("ocr")
def ocr_cmd(
    manifest_or_collection: str = typer.Argument(
        ..., help="IIIF Presentation 2.x manifest or collection JSON path or URL"
    ),
    model: str = typer.Option(
        ..., "--model", help="Kraken model ref: DOI, installed model name, or filesystem path"
    ),
    out: Path = typer.Option(
        ..., "--out", help="Output JSONL path (appends per-page records immediately)"
    ),
    max_pages: int | None = typer.Option(
        None, "--max-pages", help="Optional cap on number of canvases/pages per manifest"
    ),
    cache_dir: Path = typer.Option(
        Path(".barnacle-cache"), "--cache-dir", help="Cache directory for downloaded images"
    ),
    size: str = typer.Option(DEFAULT_IIIF_SIZE, help="IIIF size parameter"),
    fmt: str = typer.Option(DEFAULT_IIIF_FORMAT, help="IIIF format (e.g., jpg, png)"),
    quality: str = typer.Option(DEFAULT_IIIF_QUALITY, help="IIIF quality (e.g., default)"),
    region: str = typer.Option(DEFAULT_IIIF_REGION, help="IIIF region (e.g., full)"),
    rotation: str = typer.Option(DEFAULT_IIIF_ROTATION, help="IIIF rotation (e.g., 0)"),
    source_metadata_id: str | None = typer.Option(
        None, "--source-metadata-id", help="Optional provenance field"
    ),
    ark: str | None = typer.Option(
        None, "--ark", help="Optional provenance field"
    ),
    resume: bool = typer.Option(
        True, "--resume/--no-resume", help="Skip pages already present in the output JSONL"
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="Logging verbosity (DEBUG, INFO, WARNING, ERROR)"
    ),
    model_auto_install: bool = typer.Option(
        True, "--model-auto-install/--no-model-auto-install",
        help="If model looks like a DOI, run `kraken get` first"
    ),
    clear_cache_after: bool = typer.Option(
        False,
        "--clear-cache-after/--keep-cache",
        help="Delete downloaded images after each manifest is successfully processed",
    ),
    ocr_timeout: int = typer.Option(
        120, "--ocr-timeout", help="Per-image kraken timeout in seconds (default: 120)"
    ),
    manifest_timeout: int = typer.Option(
        60, "--manifest-timeout", help="Manifest fetch timeout in seconds (default: 60)"
    ),
) -> None:
    """
    Run Kraken OCR over a IIIF v2 manifest (or collection of manifests) and write JSONL output.

    For single manifests, output is written to the specified --out path.
    For collections, each manifest is processed separately to the same output file.

    Example:
        barnacle ocr https://example.org/manifest --model 10.5281/zenodo.10592716 --out out.jsonl --max-pages 5
    """
    global LOGGER
    LOGGER = setup_logging(log_level)

    # Expand paths
    out = out.expanduser()
    cache_dir = cache_dir.expanduser()

    # Process manifests
    manifest_count = 0
    total_pages = 0
    failed_manifests = []

    for manifest_id, manifest in iter_manifests(manifest_or_collection):
        manifest_count += 1
        typer.echo(f"\n📄 Processing manifest {manifest_count}: {manifest_id}")

        # Use pipeline worker for single manifest processing
        result = process_manifest(
            manifest_id=manifest_id,
            output_path=out,
            model=model,
            cache_dir=cache_dir,
            max_pages=max_pages,
            resume=resume,
            size=size,
            fmt=fmt,
            quality=quality,
            region=region,
            rotation=rotation,
            source_metadata_id=source_metadata_id,
            ark=ark,
            model_auto_install=model_auto_install,
            clear_cache_after=clear_cache_after,
            ocr_timeout=ocr_timeout,
            manifest_timeout=manifest_timeout,
        )

        # Report results
        if result.validation_issues:
            typer.echo(
                f"⚠️  Validation issues ({len(result.validation_issues)}), but processing continued:",
                err=True
            )
            for issue in result.validation_issues[:5]:  # Show first 5
                typer.echo(f"  - {issue.path}: {issue.message}", err=True)
            if len(result.validation_issues) > 5:
                typer.echo(f"  ... and {len(result.validation_issues) - 5} more", err=True)

        if result.success:
            total_pages += result.pages_processed
            timeout_note = (
                f" ({result.pages_timed_out} timed out)" if result.pages_timed_out > 0 else ""
            )
            typer.echo(
                f"✅ Completed: {result.pages_processed} pages processed, "
                f"{result.pages_skipped} skipped, "
                f"{result.pages_failed} failed{timeout_note} "
                f"({result.elapsed_seconds:.1f}s)"
            )
        else:
            failed_manifests.append(manifest_id)
            typer.echo(f"❌ Failed to process manifest: {manifest_id}", err=True)
            typer.echo("  (Check log output above for error details)", err=True)

    # Final summary
    typer.echo(f"\n{'='*60}")
    typer.echo(f"📊 Summary:")
    typer.echo(f"  Manifests processed: {manifest_count}")
    typer.echo(f"  Total pages: {total_pages}")
    typer.echo(f"  Output: {out}")

    if failed_manifests:
        typer.echo(f"\n❌ Failed manifests ({len(failed_manifests)}):")
        for manifest_id in failed_manifests:
            typer.echo(f"  - {manifest_id}")
        raise typer.Exit(code=1)



@app.command("sample-image-url")
def sample_image_url_cmd(
    manifest_or_collection: str = typer.Argument(..., help="Manifest or Collection JSON path or URL"),
    size: str = typer.Option(DEFAULT_IIIF_SIZE, help="IIIF size parameter"),
    fmt: str = typer.Option(DEFAULT_IIIF_FORMAT, help="IIIF format (e.g., jpg, png)"),
    quality: str = typer.Option(DEFAULT_IIIF_QUALITY, help="IIIF quality (e.g., default)"),
    region: str = typer.Option(DEFAULT_IIIF_REGION, help="IIIF region (e.g., full)"),
    rotation: str = typer.Option(DEFAULT_IIIF_ROTATION, help="IIIF rotation (e.g., 0)"),
) -> None:
    """Print a sample IIIF Image API URL derived from the manifest or collection."""
    # Iterate through manifests (handles both single manifests and collections)
    for manifest_id, manifest in iter_manifests(manifest_or_collection):
        canvases = manifest.canvases()
        if not canvases:
            continue

        # Get first canvas with image service
        for canvas in canvases:
            url = canvas.image_url(
                size=size,
                fmt=fmt,
                quality=quality,
                region=region,
                rotation=rotation,
            )
            if url:
                typer.echo(url)
                raise typer.Exit(code=0)

    typer.echo("Could not find an Image API service @id in any manifest.", err=True)
    raise typer.Exit(code=2)


@app.command("report-batch")
def report_batch_cmd(
    manifest_list: Path = typer.Argument(..., help="Manifest list file (one URL per line)"),
    output_dir: Path = typer.Argument(..., help="Directory containing JSONL/sidecar output files"),
    out: Path = typer.Option(Path("report.csv"), "--out", help="Output CSV path"),
) -> None:
    """
    Summarise batch OCR progress across a manifest list.

    Reads {sha1}.run.json sidecars from OUTPUT_DIR and writes one CSV row per manifest.

    Example:
        barnacle report-batch tranche-03.txt /path/to/ocr --out /tmp/batch.csv
    """
    import csv

    manifest_list = manifest_list.expanduser()
    output_dir = output_dir.expanduser()
    out = out.expanduser()

    if not manifest_list.exists():
        typer.echo(f"Error: manifest list not found: {manifest_list}", err=True)
        raise typer.Exit(code=1)

    urls = []
    with manifest_list.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)

    fieldnames = [
        "manifest_url", "total_pages", "pages_processed", "pages_failed",
        "pages_timed_out", "completion_pct", "total_time_s", "avg_time_per_page_s", "status",
    ]

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for url in urls:
            jsonl_path = manifest_output_path(url, output_dir)
            sidecar = run_report_path(jsonl_path)

            if not sidecar.exists():
                writer.writerow({
                    "manifest_url": url,
                    "total_pages": "",
                    "pages_processed": 0,
                    "pages_failed": "",
                    "pages_timed_out": "",
                    "completion_pct": "",
                    "total_time_s": "",
                    "avg_time_per_page_s": "",
                    "status": "missing",
                })
                continue

            try:
                data = json.loads(sidecar.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as e:
                typer.echo(f"Warning: could not read sidecar for {url}: {e}", err=True)
                writer.writerow({
                    "manifest_url": url,
                    "total_pages": "",
                    "pages_processed": 0,
                    "pages_failed": "",
                    "pages_timed_out": "",
                    "completion_pct": "",
                    "total_time_s": "",
                    "avg_time_per_page_s": "",
                    "status": "missing",
                })
                continue

            total = data.get("pages_total_in_manifest", 0)
            processed = data.get("pages_processed", 0)
            skipped = data.get("pages_skipped", 0)
            failed = data.get("pages_failed", "")
            timed_out = data.get("pages_timed_out", "")
            elapsed = data.get("total_elapsed_s", "")

            if total and (processed + skipped) == total:
                status = "complete"
            else:
                status = "partial"

            completion_pct = round((processed + skipped) / total * 100, 1) if total else ""
            avg_time = round(elapsed / processed, 2) if (elapsed != "" and processed) else ""

            writer.writerow({
                "manifest_url": url,
                "total_pages": total if total else "",
                "pages_processed": processed,
                "pages_failed": failed,
                "pages_timed_out": timed_out,
                "completion_pct": completion_pct,
                "total_time_s": elapsed,
                "avg_time_per_page_s": avg_time,
                "status": status,
            })

    typer.echo(f"Wrote {len(urls)} rows to {out}")


@app.command("report-manifest")
def report_manifest_cmd(
    manifest_url: str = typer.Argument(..., help="IIIF manifest URL"),
    output_dir: Path = typer.Argument(..., help="Directory containing JSONL/sidecar output files"),
    out: Path | None = typer.Option(None, "--out", help="Output CSV path (default: {sha1}_report.csv)"),
) -> None:
    """
    Per-page detail report for a single manifest.

    Reads the sidecar and JSONL output for MANIFEST_URL and writes one CSV row per canvas.

    Example:
        barnacle report-manifest https://figgy.princeton.edu/.../manifest /path/to/ocr
    """
    import csv

    output_dir = output_dir.expanduser()
    jsonl_path = manifest_output_path(manifest_url, output_dir)
    sidecar_path = run_report_path(jsonl_path)

    if not sidecar_path.exists():
        typer.echo(f"Error: no sidecar found at {sidecar_path}", err=True)
        raise typer.Exit(code=1)

    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        typer.echo(f"Error: could not read sidecar: {e}", err=True)
        raise typer.Exit(code=1)

    if out is None:
        sha1 = jsonl_path.stem
        out = Path(f"{sha1}_report.csv")
    out = out.expanduser()

    # Build lookup structures
    failure_by_index: dict[int, dict] = {}
    for f in sidecar.get("failures", []):
        ci = f.get("canvas_index")
        if ci is not None:
            failure_by_index[ci] = f

    # Read JSONL for processed page details
    records = read_jsonl_records(jsonl_path)
    processed_by_index: dict[int, dict] = {
        r["canvas_index"]: r for r in records if "canvas_index" in r
    }

    total = sidecar.get("pages_total_in_manifest", 0)
    all_indices = set(processed_by_index.keys()) | set(failure_by_index.keys())
    # Ensure we cover all indices up to total if total is known
    if total:
        all_indices = all_indices | set(range(total))

    fieldnames = ["canvas_index", "image_url", "status", "elapsed_ms", "text_length"]

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for ci in sorted(all_indices):
            if ci in processed_by_index:
                rec = processed_by_index[ci]
                writer.writerow({
                    "canvas_index": ci,
                    "image_url": rec.get("image_url", ""),
                    "status": "processed",
                    "elapsed_ms": rec.get("elapsed_ms", ""),
                    "text_length": len(rec.get("text", "")) if "text" in rec else "",
                })
            elif ci in failure_by_index:
                f = failure_by_index[ci]
                writer.writerow({
                    "canvas_index": ci,
                    "image_url": f.get("image_url") or "",
                    "status": f.get("reason", "unknown"),
                    "elapsed_ms": "",
                    "text_length": "",
                })
            else:
                # Canvas index in range but no record — skipped (resume) or not yet run
                writer.writerow({
                    "canvas_index": ci,
                    "image_url": "",
                    "status": "skipped",
                    "elapsed_ms": "",
                    "text_length": "",
                })

    typer.echo(f"Wrote report to {out}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
