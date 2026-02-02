# Batch Processing with GNU Parallel

This guide covers running Barnacle batch processing on Ubuntu VMs or similar environments using GNU Parallel as an alternative to SLURM.

## Overview

For environments without HPC job schedulers (SLURM, PBS, etc.), GNU Parallel provides a simple way to process IIIF collections in parallel. The `scripts/batch_process.sh` wrapper handles:

- Parallel execution with configurable worker count
- Job logging for progress tracking
- Resume support for interrupted runs
- Optional tmux session management for long-running jobs
- Graceful Ctrl+C shutdown

## Prerequisites

### Install GNU Parallel

**Ubuntu/Debian:**
```bash
sudo apt install parallel
```

**macOS:**
```bash
brew install parallel
```

**RHEL/CentOS/Fedora:**
```bash
sudo dnf install parallel
```

After first run, you may see a citation notice. Run this to suppress it:
```bash
parallel --citation
```

### Install Barnacle

Follow the main README installation instructions:
```bash
git clone https://github.com/pulibrary/barnacle.git
cd barnacle
pdm install
pdm run kraken get 10.5281/zenodo.14585602
```

### Optional: tmux for Long Jobs

For running jobs that may take hours or days:
```bash
sudo apt install tmux
```

## Quick Start

### 1. Prepare Manifest List

Generate a manifest list from an IIIF Collection:
```bash
python scripts/prepare_collection.py \
    https://example.org/collection/lapidus \
    --manifest-list manifests.txt \
    --output-dir ./output
```

Or from a CSV file:
```bash
python scripts/prepare_collection.py \
    data/manifests.csv \
    --csv \
    --manifest-list manifests.txt \
    --output-dir ./output
```

### 2. Run Batch Processing

```bash
./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602
```

This will:
- Process manifests in parallel (default: half of available CPUs)
- Show progress as jobs complete
- Write a job log (e.g., `batch_20260122_143052.log`)
- Create JSONL output files in the paths specified in manifests.txt

## Full Workflow

### Step 1: Prepare Your Environment

```bash
# Clone and install
git clone https://github.com/pulibrary/barnacle.git
cd barnacle
pdm install

# Download the OCR model
pdm run kraken get 10.5281/zenodo.14585602

# Create output directory
mkdir -p output
```

### Step 2: Generate Manifest List

```bash
# From IIIF Collection
python scripts/prepare_collection.py \
    https://figgy.princeton.edu/collections/lapidus/manifest \
    --manifest-list manifests.txt \
    --output-dir ./output

# Check the generated list
head manifests.txt
wc -l manifests.txt
```

### Step 3: Test with Small Batch

Before processing the full collection, test with a few manifests:
```bash
# Create test subset
head -5 manifests.txt > test_manifests.txt

# Run test batch
./scripts/batch_process.sh \
    --manifest-list test_manifests.txt \
    --model 10.5281/zenodo.14585602 \
    --jobs 2

# Verify outputs
ls -la output/*.jsonl
```

### Step 4: Run Full Batch

```bash
./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602 \
    --jobs 8
```

## Running Long Jobs

For jobs that may run for hours or days, use one of these approaches to prevent disconnection issues.

### Option 1: tmux (Recommended)

```bash
# Start in tmux session
./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602 \
    --tmux

# Detach from session: Ctrl+B, then D
# Reattach later:
tmux attach -t barnacle
```

### Option 2: Manual tmux

```bash
# Start new tmux session
tmux new -s barnacle

# Run the batch process
./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602

# Detach: Ctrl+B, then D
# Reattach: tmux attach -t barnacle
```

### Option 3: screen

```bash
# Start screen session
screen -S barnacle

# Run the batch process
./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602

# Detach: Ctrl+A, then D
# Reattach: screen -r barnacle
```

### Option 4: nohup

```bash
# Run in background with output logging
nohup ./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602 \
    > batch_output.log 2>&1 &

# Check progress
tail -f batch_output.log
```

## Monitoring Progress

### During Processing

GNU Parallel shows a progress bar by default:
```
Computers / CPU cores / Max jobs to run
1:local / 8 / 4

Computer:jobs running/jobs completed/%teleocal%/ETA:
1:4/23/65%/0:05:32
```

### Check Job Log

The job log tracks every job's status:
```bash
# View job log
cat batch_20260122_143052.log

# Count completed jobs
grep -c "^1" batch_20260122_143052.log

# Find failed jobs
awk '$7 != 0' batch_20260122_143052.log
```

Job log columns:
1. Sequence number
2. Host
3. Start time (epoch)
4. Run time (seconds)
5. Transfer time
6. Bytes transferred
7. Exit code (0 = success)
8. Signal
9. Command

### Count Outputs

```bash
# Count completed JSONL files
ls output/*.jsonl | wc -l

# Check total lines (pages processed)
wc -l output/*.jsonl
```

## Resuming Interrupted Batches

If processing is interrupted (Ctrl+C, system reboot, etc.), resume with:

```bash
./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602 \
    --resume \
    --joblog batch_20260122_143052.log
```

The `--resume` flag tells GNU Parallel to:
- Read the existing job log
- Skip successfully completed jobs
- Retry failed jobs
- Continue with unprocessed jobs

**Note:** Barnacle's `--resume` flag (enabled by default) also handles page-level resume within a manifest, so interrupted manifests will resume from the last completed page.

## Troubleshooting

### "parallel: command not found"

GNU Parallel is not installed:
```bash
sudo apt install parallel
```

### "barnacle: command not found"

Barnacle is not in PATH. Either:
```bash
# Activate virtual environment
source .venv/bin/activate
./scripts/batch_process.sh ...

# Or use pdm run
pdm run ./scripts/batch_process.sh ...
```

### Jobs Failing with Memory Errors

Reduce parallelism to lower memory pressure:
```bash
./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602 \
    --jobs 2
```

### Jobs Failing with Network Errors

IIIF servers may rate-limit requests. Reduce parallelism:
```bash
./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602 \
    --jobs 4
```

### Checking Failed Jobs

```bash
# Find failed jobs in log
awk '$7 != 0 {print $0}' batch_20260122_143052.log

# Get manifest URLs that failed
awk -F'\t' '$7 != 0 {print $9}' batch_20260122_143052.log

# Resume just the failed jobs
./scripts/batch_process.sh \
    --manifest-list manifests.txt \
    --model 10.5281/zenodo.14585602 \
    --resume \
    --joblog batch_20260122_143052.log
```

### tmux Session Already Exists

```bash
# Attach to existing session
tmux attach -t barnacle

# Or kill it and start fresh
tmux kill-session -t barnacle
```

## Command Reference

```
./scripts/batch_process.sh --help

Usage:
  ./scripts/batch_process.sh --manifest-list <FILE> --model <MODEL> [OPTIONS]

Required Arguments:
  --manifest-list <FILE>   Path to manifest list file (TSV: manifest_url, output_path)
  --model <MODEL>          Kraken model reference (DOI or path)

Options:
  --jobs <N>               Number of parallel workers (default: nproc/2)
  --joblog <FILE>          Path to job log file (default: batch_YYYYMMDD_HHMMSS.log)
  --resume                 Resume from previous joblog (use with --joblog)
  --tmux                   Start processing in a new tmux session
  -h, --help               Show this help message
```

## Comparison with SLURM

| Feature | GNU Parallel | SLURM |
|---------|--------------|-------|
| **Environment** | Any Linux/macOS | HPC cluster with SLURM |
| **Setup** | `apt install parallel` | Cluster configuration |
| **Parallelism** | Single machine | Multi-node cluster |
| **Job Management** | Job log file | SLURM job arrays |
| **Resume** | `--resume-failed` | Resubmit failed tasks |
| **Resource Limits** | Manual (--jobs N) | SLURM resource allocation |
| **Monitoring** | Progress bar, job log | squeue, sacct |
| **Best For** | Small/medium batches, VMs | Large collections, HPC |

### When to Use GNU Parallel

- Processing on a single VM or workstation
- Small to medium collections (hundreds of manifests)
- Environments without SLURM
- Quick testing before HPC deployment

### When to Use SLURM

- Large collections (thousands of manifests)
- Access to HPC cluster resources
- Need for multi-node parallelism
- Production workflows with monitoring

## See Also

- [SLURM Deployment Guide](slurm.md) - HPC cluster deployment
- [Docker Deployment Guide](docker.md) - Container builds
- [Deployment Plan](deployment-plan.md) - Full architecture design
