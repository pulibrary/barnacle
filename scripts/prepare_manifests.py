#!/usr/bin/env python3
"""Validate manifest URLs from a CSV and write valid URLs to a text file.

This script reads manifest URLs from a CSV file, validates each one is
reachable, expands any collections into their sub-manifests, and writes
the valid manifest URLs to a plain text file (one per line).

Run this when the source CSV changes. The output file can be checked into
version control.

Usage:
    python scripts/prepare_manifests.py data/lapidus_lar.csv -o manifests.txt
"""

import csv
from pathlib import Path

import typer

from barnacle.iiif.v2 import iter_manifests


app = typer.Typer(
    help="Validate manifest URLs and write to a text file",
    add_completion=False,
)


@app.command()
def main(
    csv_file: Path = typer.Argument(
        ...,
        help="Path to CSV file with 'manifest_url' column",
    ),
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help="Output file for valid manifest URLs (one per line)",
    ),
) -> None:
    """
    Validate manifest URLs from CSV and write valid URLs to a text file.

    For each URL in the CSV:
    - Validates the URL is reachable
    - Expands collections into sub-manifests
    - Logs unreachable URLs to stderr

    Example:
        python scripts/prepare_manifests.py data/lapidus_lar.csv -o manifests.txt
    """
    typer.echo(f"Reading CSV: {csv_file}")

    if not csv_file.exists():
        typer.echo(f"Error: CSV file not found: {csv_file}", err=True)
        raise typer.Exit(code=1)

    manifest_urls: list[str] = []
    skipped: list[tuple[str, str]] = []  # (url, reason)
    expanded_count = 0

    with csv_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "manifest_url" not in (reader.fieldnames or []):
            typer.echo(
                "Error: CSV file must have 'manifest_url' column", err=True
            )
            raise typer.Exit(code=1)

        for row in reader:
            url = row["manifest_url"].strip()
            if not url:
                continue

            try:
                # Use iter_manifests to handle both manifests and collections
                # This validates reachability and expands collections
                for manifest_id, _manifest in iter_manifests(url):
                    manifest_urls.append(manifest_id)
                    if manifest_id != url:
                        expanded_count += 1
            except Exception as e:
                skipped.append((url, str(e)))
                typer.echo(f"  Skipped: {url} ({e})", err=True)

    # Report skipped URLs
    if skipped:
        typer.echo(f"\nSkipped {len(skipped)} unreachable URLs", err=True)

    # Report expansion
    if expanded_count > 0:
        typer.echo(f"Expanded {expanded_count} sub-manifests from collections")

    if not manifest_urls:
        typer.echo("Error: No valid manifest URLs found", err=True)
        raise typer.Exit(code=1)

    # Write manifest URLs (one per line)
    with output.open("w") as f:
        for url in manifest_urls:
            f.write(f"{url}\n")

    typer.secho(
        f"\nWrote {len(manifest_urls)} manifest URLs to {output}",
        fg=typer.colors.GREEN,
        bold=True,
    )


if __name__ == "__main__":
    app()
