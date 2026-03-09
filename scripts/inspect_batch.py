"""
Inspect all manifests in lapidus_lar.csv and extract IIIF metadata.

Outputs a CSV with one row per manifest (expanding collections into their
constituent manifests). For child manifests that are part of a collection,
catalog metadata (source_metadata_id, ark) is inherited from the parent
collection record and parent_manifest_url is set to the collection URL.

Requires only the Python standard library; runs on Python 3.6+.

Usage:
    python3 scripts/inspect_batch.py data/lapidus_lar.csv
    python3 scripts/inspect_batch.py data/lapidus_lar.csv --output data/lapidus_metadata.csv
    python3 scripts/inspect_batch.py data/lapidus_lar.csv --output data/lapidus_metadata.csv --resume
"""

import argparse
import csv
import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path


FIELDS = [
    "manifest_url",
    "parent_manifest_url",
    "source_metadata_id",
    "ark",
    "dpul_url",
    "title",
    "creator",
    "date",
    "language",
    "publisher",
    "extent",
    "size_cm",
    "content_type",
    "collections",
    "subject",
    "page_count",
    "error",
]

# Map IIIF metadata labels to output column names (case-insensitive).
# Earlier entries take priority when multiple labels map to the same column.
LABEL_MAP = {
    "title": "title",
    "creator": "creator",
    "author": "creator",
    "date": "date",
    "language": "language",
    "publisher": "publisher",
    "extent": "extent",
    "content type": "content_type",
    "subject": "subject",
    "member of collections": "collections",
}


def ark_to_dpul_url(ark):
    return "https://dpul.princeton.edu/lapidus2025/catalog/" + ark.split("/")[-1] if ark else ""


def fetch_json(url, timeout=30):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_string(value):
    """Normalize a IIIF metadata value to a plain string.

    Handles three forms:
    - plain string: returned as-is
    - list of strings/dicts: joined with '; '
    - language-tagged object {"@value": "...", "@language": "..."}: @value extracted
    """
    if isinstance(value, dict):
        return str(value.get("@value", value)).strip()
    if isinstance(value, list):
        return "; ".join(extract_string(v) for v in value)
    return str(value).strip()


def parse_iiif_metadata(data):
    """Extract IIIF metadata array into a flat dict keyed by output column name."""
    result = {}
    for item in data.get("metadata", []):
        raw_label = item.get("label", "")
        label = extract_string(raw_label).lower()
        value = extract_string(item.get("value", ""))
        col = LABEL_MAP.get(label)
        if col and col not in result:
            result[col] = value
    return result


def parse_size_cm(extent):
    """Extract cm dimension from an extent string, e.g. '[24], 1131 p. ; 29 cm' -> '29'."""
    if not extent:
        return ""
    m = re.search(r"(\d+)\s*cm", extent)
    return m.group(1) if m else ""


def count_canvases(data):
    sequences = data.get("sequences", [])
    if not sequences:
        return 0
    return len(sequences[0].get("canvases", []))


def build_row(manifest_url, data, catalog_row, parent_manifest_url=""):
    """Build a result row dict from a fetched manifest JSON."""
    meta = parse_iiif_metadata(data)
    extent = meta.get("extent", "")
    ark = catalog_row.get("ark", "")
    return {
        "manifest_url": manifest_url,
        "parent_manifest_url": parent_manifest_url,
        "source_metadata_id": catalog_row.get("source_metadata_id", ""),
        "ark": ark,
        "dpul_url": ark_to_dpul_url(ark) if not parent_manifest_url else "",
        "title": meta.get("title", ""),
        "creator": meta.get("creator", ""),
        "date": meta.get("date", ""),
        "language": meta.get("language", ""),
        "publisher": meta.get("publisher", ""),
        "extent": extent,
        "size_cm": parse_size_cm(extent),
        "content_type": meta.get("content_type", ""),
        "collections": meta.get("collections", ""),
        "subject": meta.get("subject", ""),
        "page_count": count_canvases(data),
        "error": "",
    }


def error_row(manifest_url, catalog_row, error, parent_manifest_url=""):
    row = {f: "" for f in FIELDS}
    row["manifest_url"] = manifest_url
    row["parent_manifest_url"] = parent_manifest_url
    row["source_metadata_id"] = catalog_row.get("source_metadata_id", "")
    ark = catalog_row.get("ark", "")
    row["ark"] = ark
    row["dpul_url"] = ark_to_dpul_url(ark) if not parent_manifest_url else ""
    row["error"] = str(error)
    return row


def main():
    parser = argparse.ArgumentParser(
        description="Inspect manifests and extract IIIF metadata into a CSV"
    )
    parser.add_argument(
        "catalog",
        type=Path,
        help="CSV with columns: source_metadata_id, ark, manifest_url (e.g. data/lapidus_lar.csv)",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=None,
        help="CSV output file (default: stdout)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip manifest_urls already present in the output file",
    )
    args = parser.parse_args()

    with open(str(args.catalog), newline="", encoding="utf-8") as f:
        catalog_rows = list(csv.DictReader(f))

    # Collect already-processed URLs when resuming.
    # Only skip rows that succeeded (empty error field); error rows are retried.
    done = set()
    if args.resume and args.output and args.output.exists():
        n_errors = 0
        with open(str(args.output), newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if not row.get("error", "").strip():
                    done.add(row["manifest_url"])
                else:
                    n_errors += 1
        print("Resuming: {} succeeded, {} errors will be retried".format(
            len(done), n_errors), file=sys.stderr)

    # If resuming, rewrite the output file keeping only successful rows,
    # then append from where we left off. This removes stale error rows
    # that will be retried in this run.
    if done and args.output and args.output.exists():
        tmp = args.output.with_suffix(".tmp")
        with open(str(args.output), newline="", encoding="utf-8") as src, \
             open(str(tmp), "w", newline="", encoding="utf-8") as dst:
            reader = csv.DictReader(src)
            writer_tmp = csv.DictWriter(dst, fieldnames=FIELDS)
            writer_tmp.writeheader()
            for row in reader:
                if not row.get("error", "").strip():
                    writer_tmp.writerow(row)
        tmp.replace(args.output)

    append_mode = bool(done)
    if args.output:
        out = open(str(args.output), "a" if append_mode else "w", newline="", encoding="utf-8")
    else:
        out = sys.stdout

    try:
        writer = csv.DictWriter(out, fieldnames=FIELDS)
        if not append_mode:
            writer.writeheader()
            out.flush()

        total = len(catalog_rows)
        n_written = 0
        n_failed = 0

        for i, catalog_row in enumerate(catalog_rows, 1):
            url = catalog_row["manifest_url"].strip()
            print("[{}/{}] {}".format(i, total, url), file=sys.stderr)

            if url in done:
                print("  skipped (already done)", file=sys.stderr)
                continue

            try:
                data = fetch_json(url)
                root_type = data.get("@type", "")

                if root_type == "sc:Collection":
                    children = data.get("manifests", [])
                    print("  collection: {} child manifests".format(len(children)), file=sys.stderr)
                    for child in children:
                        child_url = child.get("@id", "").strip()
                        if not child_url:
                            continue
                        if child_url in done:
                            print("  skipped child: {}".format(child_url), file=sys.stderr)
                            continue
                        try:
                            child_data = fetch_json(child_url)
                            row = build_row(child_url, child_data, catalog_row,
                                            parent_manifest_url=url)
                        except Exception as e:
                            print("  ERROR (child {})  {}".format(child_url, e), file=sys.stderr)
                            row = error_row(child_url, catalog_row, e, parent_manifest_url=url)
                            n_failed += 1
                        writer.writerow(row)
                        out.flush()
                        n_written += 1

                elif root_type == "sc:Manifest":
                    row = build_row(url, data, catalog_row)
                    writer.writerow(row)
                    out.flush()
                    n_written += 1

                else:
                    msg = "Unexpected @type: {}".format(root_type) if root_type else "Missing @type"
                    print("  ERROR: {}".format(msg), file=sys.stderr)
                    writer.writerow(error_row(url, catalog_row, msg))
                    out.flush()
                    n_failed += 1

            except Exception as e:
                print("  ERROR: {}".format(e), file=sys.stderr)
                writer.writerow(error_row(url, catalog_row, e))
                out.flush()
                n_failed += 1

    finally:
        if args.output:
            out.close()

    print("\n--- Summary ---", file=sys.stderr)
    print("Catalog entries processed: {}".format(total), file=sys.stderr)
    print("Manifest rows written:     {}".format(n_written), file=sys.stderr)
    print("Errors:                    {}".format(n_failed), file=sys.stderr)


if __name__ == "__main__":
    main()
