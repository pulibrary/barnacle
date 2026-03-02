"""
Count pages (canvases) for each manifest in a manifest list.

Outputs a CSV with one row per manifest: url, page_count.
Prints summary statistics to stderr.

Requires only the Python standard library; runs on the cluster (Python 3.6+)
or locally without needing the barnacle package.

Usage:
    python3 scripts/count_pages.py data/manifests/tranche-01.txt
    python3 scripts/count_pages.py data/manifests/tranche-01.txt --output counts.csv
    python3 scripts/count_pages.py data/manifests/tranche-01.txt --output counts.csv --errors errors.txt
"""

import argparse
import csv
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path


def count_canvases(url):
    """Fetch a IIIF v2 manifest and return its canvas count."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    sequences = data.get("sequences", [])
    if not sequences:
        return 0
    return len(sequences[0].get("canvases", []))


def main():
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

    rows = []
    failed = []

    for i, url in enumerate(urls, 1):
        print("[{}/{}] {}".format(i, len(urls), url), file=sys.stderr)
        try:
            count = count_canvases(url)
            rows.append((url, count))
        except Exception as e:
            print("  ERROR: {}".format(e), file=sys.stderr)
            failed.append(url)

    # Write CSV
    if args.output:
        out = open(str(args.output), "w", newline="", encoding="utf-8")
    else:
        out = sys.stdout
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
        counts = sorted(r[1] for r in rows)
        n = len(counts)
        total = sum(counts)
        print("\n--- Summary ---", file=sys.stderr)
        print("Manifests:  {}".format(n), file=sys.stderr)
        print("Failed:     {}".format(len(failed)), file=sys.stderr)
        print("Total pages:{:>8,}".format(total), file=sys.stderr)
        print("Mean:       {:>8.1f}".format(total / n), file=sys.stderr)
        print("Min:        {:>8,}".format(counts[0]), file=sys.stderr)
        print("Median:     {:>8,}".format(counts[n // 2]), file=sys.stderr)
        print("Max:        {:>8,}".format(counts[-1]), file=sys.stderr)
        print("p90:        {:>8,}".format(counts[int(n * 0.9)]), file=sys.stderr)


if __name__ == "__main__":
    main()
