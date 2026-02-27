#!/usr/bin/env python3
"""Find manifests that need reprocessing after a failed or timed-out run.

Uses two complementary checks:

1. File check (always): manifests whose output JSONL is missing or empty.
   These jobs never started, or started and produced no output.

2. Log check (optional, --logs-dir): scans *.out files for jobs that ran
   but did not print "SUCCESS". Catches jobs killed by SLURM's time limit
   or that exited non-zero after writing partial output.

NOTE: Do NOT use .err files to detect failures. Barnacle's Python logging
(INFO level) writes to stderr, so every job -- including successful ones --
produces a non-empty .err file.

Usage:
    python3 scripts/find_incomplete.py MANIFEST_LIST OUTPUT_DIR [--logs-dir DIR]

Arguments:
    MANIFEST_LIST   Path to manifest list file (one URL per line)
    OUTPUT_DIR      Directory where barnacle writes output JSONL files

Options:
    --logs-dir DIR  Directory containing SLURM *.out log files. When given,
                    also reports manifests whose log exists but lacks "SUCCESS".

Output:
    Prints URLs to stdout, one per line (deduplicated, original order preserved).
    A summary line is written to stderr.

Examples:
    # File check only (catches never-started manifests):
    python3 scripts/find_incomplete.py \\
        ~/barnacle/data/manifests/tranche-01.txt \\
        /cluster/tufts/lapidusocr/shared/ocr \\
        > ~/barnacle/data/manifests/tranche-01-recovery.txt

    # Full check including timed-out jobs:
    python3 scripts/find_incomplete.py \\
        ~/barnacle/data/manifests/tranche-01.txt \\
        /cluster/tufts/lapidusocr/shared/ocr \\
        --logs-dir /cluster/tufts/lapidusocr/cwulfm01/logs \\
        > ~/barnacle/data/manifests/tranche-01-recovery.txt

    wc -l ~/barnacle/data/manifests/tranche-01-recovery.txt
"""

from __future__ import print_function

import glob
import hashlib
import os
import sys


def compute_output_path(url, output_dir):
    sha1_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()
    return os.path.join(output_dir, sha1_hash + ".jsonl")


def file_is_incomplete(url, output_dir):
    """Return True if the output JSONL is missing or empty."""
    path = compute_output_path(url, output_dir)
    return not os.path.exists(path) or os.path.getsize(path) == 0


def find_failed_urls_in_logs(logs_dir):
    """
    Scan *.out files for barnacle jobs that ran but did not succeed.

    A job is considered failed/incomplete if its .out file contains a
    "Manifest URL:" line (i.e. it is a barnacle log) but does not contain
    the word "SUCCESS" (printed only on clean exit).

    Returns a set of manifest URLs.
    """
    failed = set()
    pattern = os.path.join(logs_dir, "*.out")
    for log_path in glob.glob(pattern):
        try:
            with open(log_path) as f:
                contents = f.read()
        except OSError:
            continue

        if "Manifest URL:" not in contents:
            # Not a barnacle log (could be from another job)
            continue

        if "SUCCESS" in contents:
            continue

        # Extract the manifest URL from the log header line
        for line in contents.splitlines():
            if line.startswith("Manifest URL:"):
                url = line.split("Manifest URL:", 1)[1].strip()
                if url:
                    failed.add(url)
                break

    return failed


def parse_args(argv):
    if len(argv) < 3:
        return None, None, None

    manifest_list = argv[1]
    output_dir = argv[2]
    logs_dir = None

    i = 3
    while i < len(argv):
        if argv[i] == "--logs-dir" and i + 1 < len(argv):
            logs_dir = argv[i + 1]
            i += 2
        else:
            return None, None, None

    return manifest_list, output_dir, logs_dir


def main():
    manifest_list, output_dir, logs_dir = parse_args(sys.argv)

    if manifest_list is None:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(manifest_list):
        print("Error: manifest list not found: {}".format(manifest_list), file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(output_dir):
        print("Error: output directory not found: {}".format(output_dir), file=sys.stderr)
        sys.exit(1)

    if logs_dir is not None and not os.path.isdir(logs_dir):
        print("Error: logs directory not found: {}".format(logs_dir), file=sys.stderr)
        sys.exit(1)

    with open(manifest_list) as f:
        urls = [line.rstrip("\n") for line in f if line.strip()]

    # URLs known to have failed from log scan (may include URLs not in this
    # manifest list if logs_dir contains logs from multiple tranches)
    log_failures = set()
    if logs_dir is not None:
        log_failures = find_failed_urls_in_logs(logs_dir)
        print(
            "Log scan: {} failed/timed-out jobs found in {}".format(
                len(log_failures), logs_dir
            ),
            file=sys.stderr,
        )

    # Walk the manifest list in order, emitting each incomplete URL once
    seen = set()
    incomplete = 0
    for url in urls:
        if url in seen:
            continue
        if file_is_incomplete(url, output_dir) or url in log_failures:
            print(url)
            seen.add(url)
            incomplete += 1

    print(
        "{} of {} manifests incomplete".format(incomplete, len(urls)),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
