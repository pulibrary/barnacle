#!/usr/bin/env python3
"""Summarize the current state of a barnacle batch run.

Reads SLURM job state and output JSONL files to report:
  - Which manifests are currently being processed
  - How many manifests and pages have been completed
  - Average time per page
  - Which manifests have failed

Usage:
    python scripts/run_stats.py \\
        --manifest-list ~/barnacle/data/manifests/tranche-01.txt \\
        --output-dir /cluster/tufts/lapidusocr/shared/ocr \\
        --job-id 12345
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path


def sha1_of_url(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()


def load_manifest_list(path: Path) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def slurm_cmd(args: list[str]) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def get_running_task_ids(job_id: str) -> list[int]:
    output = slurm_cmd(["squeue", "-j", job_id, "-t", "RUNNING", "-h", "-o", "%K"])
    ids = []
    for line in output.splitlines():
        line = line.strip()
        if line.isdigit():
            ids.append(int(line))
    return sorted(ids)


def get_failed_task_ids(job_id: str) -> list[int]:
    # -X: only top-level steps; -P: pipe-delimited; -n: no header
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


def detect_job_id() -> str | None:
    """Try to find a single running barnacle-ocr job for the current user."""
    user = os.environ.get("USER", "")
    output = slurm_cmd(
        ["squeue", "-u", user, "-n", "barnacle-ocr", "-h", "-o", "%F"]
    )
    # %F is the base job ID of an array
    job_ids = list({line.strip() for line in output.splitlines() if line.strip()})
    return job_ids[0] if len(job_ids) == 1 else None


def scan_output_dir(
    output_dir: Path, sha1_to_manifest: dict[str, tuple[int, str]]
) -> tuple[int, int, float]:
    """
    Returns (processed_count, total_pages, avg_seconds_per_page).
    Only counts files whose SHA1 matches the provided manifest list.
    """
    total_pages = 0
    total_elapsed_ms = 0
    elapsed_count = 0
    processed_count = 0

    if not output_dir.exists():
        return 0, 0, 0.0

    for jsonl_file in output_dir.glob("*.jsonl"):
        sha1 = jsonl_file.stem
        if sha1 not in sha1_to_manifest:
            continue
        processed_count += 1
        with open(jsonl_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    total_pages += 1
                    elapsed = record.get("elapsed_ms", 0)
                    if elapsed > 0:
                        total_elapsed_ms += elapsed
                        elapsed_count += 1
                except json.JSONDecodeError:
                    pass

    avg_seconds = (total_elapsed_ms / elapsed_count / 1000) if elapsed_count > 0 else 0.0
    return processed_count, total_pages, avg_seconds


def main() -> None:
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
        "--job-id", type=str,
        help="SLURM job ID (auto-detected if not provided)"
    )
    args = parser.parse_args()

    manifests = load_manifest_list(args.manifest_list)
    total_manifests = len(manifests)

    # Map SHA1 -> (1-based task ID, URL)
    sha1_to_manifest: dict[str, tuple[int, str]] = {
        sha1_of_url(url): (i + 1, url) for i, url in enumerate(manifests)
    }

    job_id = args.job_id or detect_job_id()

    running_task_ids = get_running_task_ids(job_id) if job_id else []
    failed_task_ids = get_failed_task_ids(job_id) if job_id else []

    processed_count, total_pages, avg_seconds = scan_output_dir(
        args.output_dir, sha1_to_manifest
    )

    # -------------------------------------------------------------------------
    # Output
    # -------------------------------------------------------------------------
    W = 62
    print("=" * W)
    print("Barnacle Run Statistics")
    print("=" * W)
    if job_id:
        print(f"Job ID:    {job_id}")
    print(f"Manifest:  {args.manifest_list.name}  ({total_manifests} manifests)")
    print()

    # Currently processing
    if job_id:
        print(f"Currently processing: {len(running_task_ids)} task(s)")
        for task_id in running_task_ids:
            url = manifests[task_id - 1] if 1 <= task_id <= len(manifests) else "unknown"
            print(f"  [{task_id:>4}] {url}")
        print()

    # Progress
    pct = (processed_count / total_manifests * 100) if total_manifests else 0
    print(f"Manifests completed:  {processed_count:>5} / {total_manifests}  ({pct:.1f}%)")
    print(f"Pages processed:      {total_pages:>8,}")
    if avg_seconds > 0:
        print(f"Avg time per page:    {avg_seconds:>6.1f}s")
    print()

    # Failed
    if job_id:
        print(f"Failed: {len(failed_task_ids)} task(s)")
        for task_id in failed_task_ids:
            url = manifests[task_id - 1] if 1 <= task_id <= len(manifests) else "unknown"
            print(f"  [{task_id:>4}] {url}")
    print("=" * W)


if __name__ == "__main__":
    main()
