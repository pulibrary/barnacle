"""
Create page-balanced processing tranches from a page-count CSV.

Uses greedy bin-packing (largest-first) to assign manifests to tranches
so each tranche has approximately equal total pages — giving predictable
SLURM wall-time usage.

Usage:
    python3 scripts/make_tranches.py \\
        --counts data/manifests/all_page_counts.csv \\
        --exclude data/manifests/tranche-01.txt data/manifests/tranche-02a.txt \\
        --n-tranches 6 \\
        --output-dir data/manifests \\
        --prefix tranche- \\
        --start-index 3

Outputs tranche-03.txt through tranche-08.txt (or whatever prefix/index).
Prints a summary table to stdout.
"""

import argparse
import csv
import heapq
import sys
from pathlib import Path


def load_page_counts(csv_path):
    """Return list of (url, page_count) from CSV, skipping header."""
    rows = []
    with open(str(csv_path), "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append((row["manifest_url"], int(row["page_count"])))
    return rows


def load_url_set(paths):
    """Return set of URLs from one or more manifest list files."""
    urls = set()
    for p in paths:
        with open(str(p), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.add(line)
    return urls


def fmt_hms(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return "{:d}:{:02d}:{:02d}".format(h, m, s)


def make_tranches(manifests, n):
    """
    Greedy largest-first bin packing.
    manifests: list of (url, page_count), will be sorted descending by page_count.
    Returns list of n lists, each containing (url, page_count) tuples.
    """
    # Sort largest first for better balance
    sorted_manifests = sorted(manifests, key=lambda x: x[1], reverse=True)

    # Min-heap of (total_pages, tranche_index)
    heap = [(0, i) for i in range(n)]
    heapq.heapify(heap)

    bins = [[] for _ in range(n)]
    for url, pages in sorted_manifests:
        total, idx = heapq.heappop(heap)
        bins[idx].append((url, pages))
        heapq.heappush(heap, (total + pages, idx))

    return bins


def main():
    parser = argparse.ArgumentParser(description="Create page-balanced tranches")
    parser.add_argument("--counts", type=Path,
                        default=Path("data/manifests/all_page_counts.csv"),
                        help="CSV with manifest_url,page_count columns")
    parser.add_argument("--exclude", type=Path, nargs="*", default=[],
                        help="Manifest list files whose URLs should be excluded (already processed)")
    parser.add_argument("--exclude-url", nargs="*", default=[],
                        help="Individual URLs to exclude (e.g. known-bad manifests)")
    parser.add_argument("--n-tranches", type=int, default=6,
                        help="Number of tranches to create (default: 6)")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("data/manifests"),
                        help="Directory to write tranche files (default: data/manifests)")
    parser.add_argument("--prefix", default="tranche-",
                        help="Filename prefix (default: 'tranche-')")
    parser.add_argument("--start-index", type=int, default=3,
                        help="Starting tranche number (default: 3)")
    parser.add_argument("--secs-per-page", type=float, default=53.0,
                        help="Seconds per page for wall-time estimate (default: 53)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary without writing files")
    args = parser.parse_args()

    all_rows = load_page_counts(args.counts)

    excluded = load_url_set(args.exclude) if args.exclude else set()
    for url in args.exclude_url:
        excluded.add(url)

    remaining = [(url, pages) for url, pages in all_rows if url not in excluded]

    if not remaining:
        print("ERROR: no manifests remaining after exclusions", file=sys.stderr)
        sys.exit(1)

    total_pages = sum(p for _, p in remaining)
    print("Remaining manifests: {:,}".format(len(remaining)))
    print("Remaining pages:     {:,}".format(total_pages))
    print("Target pages/tranche: ~{:,}".format(total_pages // args.n_tranches))
    print()

    bins = make_tranches(remaining, args.n_tranches)

    # Print summary table
    # Est. time = max manifest size in tranche (each SLURM task processes one manifest)
    secs_limit = 24 * 3600
    warn_threshold = int(secs_limit / args.secs_per_page)

    header = "{:<12} {:>10} {:>10} {:>10} {:>12}  {}".format(
        "File", "Manifests", "Total pg", "Max pg", "Max est.", "Wall OK?")
    print(header)
    print("-" * len(header))

    args.output_dir.mkdir(parents=True, exist_ok=True)

    for i, tranche in enumerate(bins):
        idx = args.start_index + i
        filename = "{}{:02d}.txt".format(args.prefix, idx)
        total_pg = sum(p for _, p in tranche)
        max_pg = max(p for _, p in tranche)
        est = fmt_hms(max_pg * args.secs_per_page)
        ok = "YES" if max_pg <= warn_threshold else "NO ({}p > {}h)".format(max_pg, 24)
        print("{:<12} {:>10,} {:>10,} {:>10,} {:>12}  {}".format(
            filename, len(tranche), total_pg, max_pg, est, ok))

        if not args.dry_run:
            out_path = args.output_dir / filename
            with open(str(out_path), "w", encoding="utf-8") as f:
                for url, _ in tranche:
                    f.write(url + "\n")

    if args.dry_run:
        print("\n(dry run — no files written)")
    else:
        print("\nWrote {} tranche files to {}".format(args.n_tranches, args.output_dir))


if __name__ == "__main__":
    main()
