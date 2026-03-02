"""
Count pages (canvases) for each manifest in a manifest list.

Outputs a CSV with one row per manifest: url, page_count.
Prints summary statistics to stderr.

Usage:
    python3 scripts/count_pages.py data/manifests/tranche-01.txt
    python3 scripts/count_pages.py data/manifests/tranche-01.txt --output counts.csv
    python3 scripts/count_pages.py data/manifests/tranche-01.txt --output counts.csv --errors errors.txt
"""

import argparse
import csv
import sys
from pathlib import Path

from barnacle.iiif.v2 import iter_manifests


def main() -> None:
    parser = argparse.ArgumentParser(description="Count pages per manifest")
    parser.add_argument("manifest_list", type=Path, help="File with manifest URLs (one per line)")
    parser.add_argument("--output", "-o", type=Path, default=None, help="CSV output file (default: stdout)")
    parser.add_argument("--errors", "-e", type=Path, default=None, help="File to write failed URLs to")
    args = parser.parse_args()

    urls = [
        line.strip()
        for line in args.manifest_list.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    rows: list[tuple[str, int]] = []
    failed: list[str] = []

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}", file=sys.stderr)
        try:
            for manifest_id, manifest in iter_manifests(url):
                rows.append((manifest_id, len(manifest.canvases())))
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            failed.append(url)

    # Write CSV
    out = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
    try:
        writer = csv.writer(out)
        writer.writerow(["manifest_url", "page_count"])
        writer.writerows(rows)
    finally:
        if args.output:
            out.close()

    # Write errors file
    if failed and args.errors:
        args.errors.write_text("\n".join(failed) + "\n", encoding="utf-8")

    # Summary
    if rows:
        counts = [r[1] for r in rows]
        counts_sorted = sorted(counts)
        n = len(counts)
        total = sum(counts)
        print(f"\n--- Summary ---", file=sys.stderr)
        print(f"Manifests:  {n}", file=sys.stderr)
        print(f"Failed:     {len(failed)}", file=sys.stderr)
        print(f"Total pages:{total:>8,}", file=sys.stderr)
        print(f"Mean:       {total/n:>8.1f}", file=sys.stderr)
        print(f"Min:        {counts_sorted[0]:>8,}", file=sys.stderr)
        print(f"Median:     {counts_sorted[n//2]:>8,}", file=sys.stderr)
        print(f"Max:        {counts_sorted[-1]:>8,}", file=sys.stderr)
        p90 = counts_sorted[int(n * 0.9)]
        print(f"p90:        {p90:>8,}", file=sys.stderr)


if __name__ == "__main__":
    main()
