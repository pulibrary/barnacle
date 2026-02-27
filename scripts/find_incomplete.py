#!/usr/bin/env python3
"""Find manifests with missing or empty output files.

For each URL in a manifest list, computes the expected output path using
the same SHA1 logic as barnacle (sha1(url).hexdigest() + ".jsonl") and
prints URLs whose output file is missing or empty.

Usage:
    python3 scripts/find_incomplete.py MANIFEST_LIST OUTPUT_DIR

Arguments:
    MANIFEST_LIST  Path to manifest list file (one URL per line)
    OUTPUT_DIR     Directory where barnacle writes output JSONL files

Output:
    Prints incomplete manifest URLs to stdout, one per line.
    Suitable for piping into a new manifest list for recovery submission.

Example:
    python3 scripts/find_incomplete.py \\
        ~/barnacle/data/manifests/tranche-01.txt \\
        /cluster/tufts/lapidusocr/shared/ocr \\
        > ~/barnacle/data/manifests/tranche-01-recovery.txt

    wc -l ~/barnacle/data/manifests/tranche-01-recovery.txt
"""

from __future__ import print_function

import hashlib
import os
import sys


def compute_output_path(url, output_dir):
    sha1_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return os.path.join(output_dir, sha1_hash + ".jsonl")


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    manifest_list = sys.argv[1]
    output_dir = sys.argv[2]

    if not os.path.isfile(manifest_list):
        print("Error: manifest list not found: {}".format(manifest_list), file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(output_dir):
        print("Error: output directory not found: {}".format(output_dir), file=sys.stderr)
        sys.exit(1)

    with open(manifest_list) as f:
        urls = [line.rstrip("\n") for line in f if line.strip()]

    incomplete = 0
    for url in urls:
        output_path = compute_output_path(url, output_dir)
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            print(url)
            incomplete += 1

    print(
        "{} of {} manifests incomplete".format(incomplete, len(urls)),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
