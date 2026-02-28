#!/usr/bin/env python3
"""Summarize the current state of a barnacle batch run.

Reports per-manifest status and page counts by combining three sources:
  - Output JSONL files (pages recorded per manifest)
  - SLURM .out log files (SUCCESS marker, for complete vs partial)
  - squeue / sacct (currently running and SLURM-failed tasks)

Manifest status categories:
  complete  - .out log contains "SUCCESS"
  partial   - JSONL exists and is non-empty, but no SUCCESS in log
  missing   - JSONL is absent or empty (job never started or wrote nothing)

When --logs-dir is not provided, any non-empty JSONL is counted as
"complete" (the old behaviour). Use --logs-dir to get accurate counts.

Usage:
    python3 scripts/run_stats.py \\
        --manifest-list ~/barnacle/data/manifests/tranche-01.txt \\
        --output-dir /cluster/tufts/lapidusocr/shared/ocr \\
        [--logs-dir /cluster/tufts/lapidusocr/cwulfm01/logs] \\
        [--job-id 12345]
"""

import argparse
import glob
import hashlib
import json
import os
import subprocess
from pathlib import Path


def sha1_of_url(url):
    return hashlib.sha1(url.encode()).hexdigest()


def load_manifest_list(path):
    with open(str(path)) as f:
        return [line.strip() for line in f if line.strip()]


def slurm_cmd(args):
    try:
        result = subprocess.run(
            args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15
        )
        return result.stdout.decode("utf-8")
    except (subprocess.TimeoutExpired, OSError):
        return ""


def get_running_task_ids(job_id):
    output = slurm_cmd(["squeue", "-j", job_id, "-t", "RUNNING", "-h", "-o", "%K"])
    ids = []
    for line in output.splitlines():
        line = line.strip()
        if line.isdigit():
            ids.append(int(line))
    return sorted(ids)


def get_failed_task_ids(job_id):
    output = slurm_cmd(
        ["sacct", "-j", job_id, "--format=JobID,State", "-n", "-P", "-X"]
    )
    ids = []
    for line in output.splitlines():
        parts = line.split("|")
        if len(parts) >= 2 and "FAILED" in parts[1]:
            job_id_part = parts[0].strip()
            if "_" in job_id_part:
                try:
                    ids.append(int(job_id_part.split("_")[1]))
                except ValueError:
                    pass
    return sorted(ids)


def detect_job_id():
    user = os.environ.get("USER", "")
    output = slurm_cmd(
        ["squeue", "-u", user, "-n", "barnacle-ocr", "-h", "-o", "%F"]
    )
    job_ids = list(set(line.strip() for line in output.splitlines() if line.strip()))
    return job_ids[0] if len(job_ids) == 1 else None


def scan_logs(logs_dir):
    """
    Scan *.out files and return two sets of manifest URLs:
      succeeded - log contains "SUCCESS"
      failed    - log contains "Manifest URL:" but not "SUCCESS"
    """
    succeeded = set()
    failed = set()
    pattern = os.path.join(logs_dir, "*.out")
    for log_path in glob.glob(pattern):
        try:
            with open(log_path) as f:
                contents = f.read()
        except OSError:
            continue

        if "Manifest URL:" not in contents:
            continue

        url = None
        for line in contents.splitlines():
            if line.startswith("Manifest URL:"):
                url = line.split("Manifest URL:", 1)[1].strip()
                break

        if not url:
            continue

        if "SUCCESS" in contents:
            succeeded.add(url)
        else:
            failed.add(url)

    return succeeded, failed


def read_jsonl(jsonl_path):
    """Single-pass read of a JSONL file.

    Returns (page_count, total_elapsed_ms, elapsed_count).
    """
    pages = 0
    total_elapsed_ms = 0
    elapsed_count = 0
    try:
        with open(str(jsonl_path)) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    pages += 1
                    elapsed = rec.get("elapsed_ms", 0)
                    if elapsed > 0:
                        total_elapsed_ms += elapsed
                        elapsed_count += 1
                except ValueError:
                    pass
    except OSError:
        pass
    return pages, total_elapsed_ms, elapsed_count


def main():
    parser = argparse.ArgumentParser(description="Summarize a barnacle batch run")
    parser.add_argument(
        "--manifest-list", required=True, type=Path,
        help="Path to manifest list file (one URL per line)"
    )
    parser.add_argument(
        "--output-dir", required=True, type=Path,
        help="Directory containing output JSONL files"
    )
    parser.add_argument(
        "--logs-dir", type=Path,
        help="Directory containing SLURM *.out log files (enables complete/partial distinction)"
    )
    parser.add_argument(
        "--job-id", type=str,
        help="SLURM job ID (auto-detected if not provided)"
    )
    args = parser.parse_args()

    manifests = load_manifest_list(args.manifest_list)
    total_manifests = len(manifests)

    # Scan logs if available
    log_succeeded = set()
    log_failed = set()
    have_logs = False
    if args.logs_dir:
        if not args.logs_dir.is_dir():
            print("Warning: --logs-dir not found: {}".format(args.logs_dir))
        else:
            log_succeeded, log_failed = scan_logs(str(args.logs_dir))
            have_logs = True

    job_id = args.job_id or detect_job_id()
    running_task_ids = get_running_task_ids(job_id) if job_id else []
    failed_task_ids = get_failed_task_ids(job_id) if job_id else []

    # Per-manifest accounting
    n_complete = 0
    n_partial = 0
    n_missing = 0
    total_pages = 0
    total_elapsed_ms = 0
    elapsed_count = 0

    # Rows for the incomplete-manifest table
    incomplete_rows = []  # (task_id, url, pages, status_label)

    for i, url in enumerate(manifests):
        task_id = i + 1
        sha1 = sha1_of_url(url)
        jsonl_path = args.output_dir / (sha1 + ".jsonl")

        has_output = jsonl_path.exists() and jsonl_path.stat().st_size > 0
        if has_output:
            pages, elapsed_ms, n_elapsed = read_jsonl(jsonl_path)
            total_pages += pages
            total_elapsed_ms += elapsed_ms
            elapsed_count += n_elapsed
        else:
            pages = 0

        # Determine status
        if have_logs:
            if url in log_succeeded:
                status = "complete"
                n_complete += 1
            elif has_output:
                status = "partial"
                n_partial += 1
                incomplete_rows.append((task_id, url, pages, "partial"))
            else:
                status = "missing"
                n_missing += 1
                incomplete_rows.append((task_id, url, 0, "missing"))
        else:
            # Without logs, fall back to file-based heuristic
            if has_output:
                status = "complete"
                n_complete += 1
            else:
                status = "missing"
                n_missing += 1
                incomplete_rows.append((task_id, url, 0, "missing"))

    avg_seconds = (total_elapsed_ms / elapsed_count / 1000) if elapsed_count > 0 else 0.0

    # -------------------------------------------------------------------------
    # Output
    # -------------------------------------------------------------------------
    W = 70
    print("=" * W)
    print("Barnacle Run Statistics")
    print("=" * W)
    if job_id:
        print("Job ID:    {}".format(job_id))
    print("Manifest:  {}  ({} manifests)".format(
        args.manifest_list.name, total_manifests))
    if have_logs:
        print("Logs:      {}".format(args.logs_dir))
    print()

    if job_id and running_task_ids:
        print("Currently processing: {} task(s)".format(len(running_task_ids)))
        for task_id in running_task_ids:
            url = manifests[task_id - 1] if 1 <= task_id <= len(manifests) else "unknown"
            print("  [{:>4}] {}".format(task_id, url))
        print()

    # Summary counts
    pct_complete = (n_complete / total_manifests * 100) if total_manifests else 0.0
    if have_logs:
        pct_partial = (n_partial / total_manifests * 100) if total_manifests else 0.0
        pct_missing = (n_missing / total_manifests * 100) if total_manifests else 0.0
        print("Manifests complete:   {:>4} / {}  ({:.1f}%)".format(
            n_complete, total_manifests, pct_complete))
        print("Manifests partial:    {:>4} / {}  ({:.1f}%)".format(
            n_partial, total_manifests, pct_partial))
        print("Manifests missing:    {:>4} / {}  ({:.1f}%)".format(
            n_missing, total_manifests, pct_missing))
    else:
        print("Manifests with output:{:>4} / {}  ({:.1f}%)  [use --logs-dir for complete/partial breakdown]".format(
            n_complete, total_manifests, pct_complete))
        print("Manifests missing:    {:>4} / {}".format(n_missing, total_manifests))

    print("Pages recorded:    {:>9,}".format(total_pages))
    if avg_seconds > 0:
        print("Avg time per page: {:>9.1f}s".format(avg_seconds))
    print()

    # Incomplete manifest table
    if incomplete_rows:
        print("Incomplete manifests ({} total):".format(len(incomplete_rows)))
        print("  {:<6}  {:>7}  {}  {}".format(
            "task", "pages", "status ", "url"))
        print("  {}  {}  {}  {}".format("-" * 6, "-" * 7, "-" * 7, "-" * 40))
        for task_id, url, pages, status in incomplete_rows:
            print("  [{:>4}]  {:>7}  {:<7}  {}".format(
                task_id, pages, status, url))
        print()

    if job_id and failed_task_ids:
        print("SLURM-reported failed tasks: {}".format(len(failed_task_ids)))
        for task_id in failed_task_ids:
            url = manifests[task_id - 1] if 1 <= task_id <= len(manifests) else "unknown"
            print("  [{:>4}] {}".format(task_id, url))
        print()

    print("=" * W)


if __name__ == "__main__":
    main()
