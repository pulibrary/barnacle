#!/usr/bin/env python3
"""Prepare collection for SLURM job array processing.

This script parses a IIIF Collection or Manifest and generates a manifest
list file suitable for SLURM job array execution. Each line in the output
file contains a manifest URL and its corresponding output path.

Usage:
    python scripts/prepare_collection.py <COLLECTION_URL> \\
        --manifest-list manifests.txt \\
        --output-dir /scratch/$USER/barnacle/runs/ocr

    # From CSV file with manifest_url column:
    python scripts/prepare_collection.py data/lapidus_lar.csv \\
        --csv \\
        --manifest-list manifests.txt \\
        --output-dir /scratch/$USER/barnacle/runs/ocr
"""

import csv
from pathlib import Path

import typer

from barnacle.pipeline.coordinator import prepare_manifest_list
from barnacle.pipeline.output import manifest_output_path


app = typer.Typer(
    help="Prepare IIIF Collection for parallel SLURM processing",
    add_completion=False,
)


@app.command()
def main(
    collection_or_manifest: str = typer.Argument(
        ...,
        help="URL/path to IIIF Collection/Manifest, OR path to CSV file (with --csv)",
    ),
    manifest_list: Path = typer.Option(
        ...,
        "--manifest-list",
        "-m",
        help="Output file containing manifest URLs and output paths (TSV format)",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        "-o",
        help="Directory where per-manifest JSONL output files will be written",
    ),
    csv_input: bool = typer.Option(
        False,
        "--csv",
        help="Treat input as CSV file with 'manifest_url' column",
    ),
) -> None:
    """
    Parse IIIF Collection and generate manifest list for SLURM job array.

    Creates:
    - manifest_list: TSV file with columns: manifest_url, output_path
    - output_dir: Directory for per-manifest JSONL files (created if needed)

    Example:
        python scripts/prepare_collection.py \\
            https://example.org/collection/123 \\
            --manifest-list manifests.txt \\
            --output-dir /scratch/user/barnacle/runs/ocr

        # From CSV file:
        python scripts/prepare_collection.py data/lapidus_lar.csv \\
            --csv \\
            --manifest-list manifests.txt \\
            --output-dir /scratch/user/barnacle/runs/ocr
    """
    try:
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        typer.echo(f"Output directory: {output_dir}")

        if csv_input:
            # Read manifest URLs from CSV file
            csv_path = Path(collection_or_manifest)
            typer.echo(f"Reading CSV: {csv_path}")

            if not csv_path.exists():
                typer.echo(f"Error: CSV file not found: {csv_path}", err=True)
                raise typer.Exit(code=1)

            manifest_urls: list[tuple[str, Path]] = []
            with csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if "manifest_url" not in (reader.fieldnames or []):
                    typer.echo(
                        "Error: CSV file must have 'manifest_url' column", err=True
                    )
                    raise typer.Exit(code=1)
                for row in reader:
                    url = row["manifest_url"].strip()
                    if url:
                        output_path = manifest_output_path(url, output_dir)
                        manifest_urls.append((url, output_path))

            if not manifest_urls:
                typer.echo("Error: No manifest URLs found in CSV", err=True)
                raise typer.Exit(code=1)

            # Write manifest list (TSV format)
            with manifest_list.open("w") as f:
                for url, out_path in manifest_urls:
                    f.write(f"{url}\t{out_path}\n")

            task_count = len(manifest_urls)
        else:
            # Parse IIIF collection and prepare task list
            typer.echo(f"Parsing: {collection_or_manifest}")
            tasks = prepare_manifest_list(collection_or_manifest, output_dir)

            if not tasks:
                typer.echo("Error: No manifests found in collection", err=True)
                raise typer.Exit(code=1)

            # Write manifest list (TSV format)
            with manifest_list.open("w") as f:
                for task in tasks:
                    f.write(f"{task.manifest_id}\t{task.output_path}\n")

            task_count = len(tasks)

        # Success summary
        typer.secho(
            f"\n✅ Prepared {task_count} manifests for processing",
            fg=typer.colors.GREEN,
            bold=True,
        )
        typer.echo(f"   Manifest list: {manifest_list}")
        typer.echo(f"   Output directory: {output_dir}")
        typer.echo(f"\nNext step:")
        typer.echo(f"   sbatch --array=1-{task_count} slurm/process_manifest.sh")

    except FileNotFoundError as e:
        typer.echo(f"Error: File not found: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
