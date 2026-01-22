#!/usr/bin/env python3
"""Prepare collection for SLURM job array processing.

This script parses a IIIF Collection or Manifest and generates a manifest
list file suitable for SLURM job array execution. Each line in the output
file contains a manifest URL and its corresponding output path.

Usage:
    python scripts/prepare_collection.py <COLLECTION_URL> \\
        --manifest-list manifests.txt \\
        --output-dir /scratch/$USER/barnacle/runs/ocr
"""

import sys
from pathlib import Path

import typer

from barnacle.pipeline.coordinator import prepare_manifest_list


app = typer.Typer(
    help="Prepare IIIF Collection for parallel SLURM processing",
    add_completion=False,
)


@app.command()
def main(
    collection_or_manifest: str = typer.Argument(
        ...,
        help="URL or path to IIIF Collection or Manifest",
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
    """
    try:
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        typer.echo(f"Output directory: {output_dir}")

        # Parse collection and prepare task list
        typer.echo(f"Parsing: {collection_or_manifest}")
        tasks = prepare_manifest_list(collection_or_manifest, output_dir)

        if not tasks:
            typer.echo("Error: No manifests found in collection", err=True)
            raise typer.Exit(code=1)

        # Write manifest list (TSV format)
        with manifest_list.open("w") as f:
            for task in tasks:
                f.write(f"{task.manifest_id}\t{task.output_path}\n")

        # Success summary
        typer.secho(
            f"\n✅ Prepared {len(tasks)} manifests for processing",
            fg=typer.colors.GREEN,
            bold=True,
        )
        typer.echo(f"   Manifest list: {manifest_list}")
        typer.echo(f"   Output directory: {output_dir}")
        typer.echo(f"\nNext step:")
        typer.echo(f"   sbatch --array=1-{len(tasks)} slurm/process_manifest.sh")

    except FileNotFoundError as e:
        typer.echo(f"Error: File not found: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
