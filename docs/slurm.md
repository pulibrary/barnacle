# SLURM Deployment Guide

This guide covers running Barnacle on HPC clusters with SLURM job scheduler.

## Overview

Barnacle uses **SLURM job arrays** for parallel manifest processing:

1. Parse IIIF Collection to extract manifest URLs
2. Generate manifest list (one manifest per line)
3. Submit SLURM job array (one array task per manifest)
4. Each array task processes one manifest independently
5. Results written to per-manifest JSONL files (resume-safe)

## Architecture

```
CSV file (manifest URLs)
    ↓
prepare_manifests.py → manifests.txt (one URL per line)
    ↓
SLURM Job Array (sbatch --array=1-N)
    ↓
    ├─ Task 1 → Manifest 1 → SHA1_hash_1.jsonl
    ├─ Task 2 → Manifest 2 → SHA1_hash_2.jsonl
    ├─ ...
    └─ Task N → Manifest N → SHA1_hash_N.jsonl
```

**Benefits**:
- Parallel processing across cluster nodes
- Per-manifest resume safety (no shared file writes)
- SLURM-native fault tolerance
- Easy to resubmit failed tasks

## Prerequisites

1. **Singularity container** built and available on cluster
   - See `docs/docker.md` for building and converting to Singularity
   - Example path: `/project/barnacle/barnacle.sif`

2. **Kraken model** downloaded and accessible
   - Example path: `/project/barnacle/models/McCATMuS_nfd_nofix_V1.mlmodel`
   - See README for model download instructions

3. **Storage paths** configured
   - Cache directory: `/scratch/$USER/barnacle/cache`
   - Output directory: `/scratch/$USER/barnacle/runs`
   - Model directory: `/project/barnacle/models`

4. **Python environment** with Barnacle installed (for `prepare_manifests.py`)
   - Can use same container or local installation

## Quick Start

### Option A: End-to-End Wrapper (Recommended)

Use `slurm/run_collection.sh` for automated workflow:

```bash
# First, generate the manifest list (run once when source CSV changes)
python scripts/prepare_manifests.py data/lapidus_lar.csv -o manifests.txt

# Set environment variables (or edit script defaults)
export CONTAINER=/project/barnacle/barnacle.sif
export MODEL_PATH=/project/barnacle/models/McCATMuS_nfd_nofix_V1.mlmodel
export CACHE_DIR=/scratch/$USER/barnacle/cache

# Run collection
./slurm/run_collection.sh manifests.txt lapidus_batch_20260122
```

This will:
1. Submit SLURM job array
2. Print monitoring commands
3. Save run metadata

### Option B: Manual Step-by-Step

For more control, run each step manually:

#### Step 1: Prepare Manifest List

Generate a validated manifest list from a CSV file:

```bash
# From CSV file with 'manifest_url' column
python scripts/prepare_manifests.py data/lapidus_lar.csv -o manifests.txt

# Outputs:
# - manifests.txt (one manifest URL per line)
```

The script:
- Validates each URL is reachable
- Expands any IIIF Collections into their sub-manifests
- Logs unreachable URLs to stderr

The CSV file must have a header row with a `manifest_url` column. Additional columns (e.g., `source_metadata_id`, `ark`) are ignored by this script but can be useful for post-processing.

Example CSV format:
```csv
source_metadata_id,ark,manifest_url
99106449843506421,ark:/88435/dckk91g0036,https://figgy.princeton.edu/concern/scanned_resources/a1c525c8-7b0c-4bc2-ad4c-709830afc16b/manifest
99106365393506421,ark:/88435/dcs7526r87k,https://figgy.princeton.edu/concern/scanned_resources/bc000721-7ef1-482e-a18e-0c2c10e67f3d/manifest
```

The manifest list can be version-controlled since it contains only URLs (output paths are computed at runtime).

#### Step 2: Submit SLURM Job Array

```bash
# Count manifests
N=$(wc -l < manifests.txt)

# Create log directory
mkdir -p logs/

# Submit job array
sbatch --array=1-$N \
    --output=logs/barnacle-%A_%a.out \
    --error=logs/barnacle-%A_%a.err \
    --export=ALL,MANIFEST_LIST=manifests.txt,MODEL_PATH=/project/barnacle/models/model.mlmodel,CONTAINER=/project/barnacle/barnacle.sif \
    slurm/process_manifest.sh
```

## Monitoring Jobs

### Check Job Status

```bash
# View all your jobs
squeue -u $USER

# View specific job array
squeue -j <JOB_ID>

# Count running/pending tasks
squeue -j <JOB_ID> -t RUNNING | wc -l
squeue -j <JOB_ID> -t PENDING | wc -l
```

### Check Completed Tasks

```bash
# Show all array tasks with exit codes
sacct -j <JOB_ID> --format=JobID,State,ExitCode,Elapsed

# Show only failed tasks
sacct -j <JOB_ID> --format=JobID,State,ExitCode | grep FAILED
```

### View Logs

```bash
# List all logs
ls logs/

# View specific array task log
cat logs/barnacle-<JOB_ID>_<ARRAY_TASK_ID>.out

# Follow first task (for testing)
tail -f logs/barnacle-<JOB_ID>_1.out

# Search for errors
grep -i error logs/barnacle-*.err
```

### Check Outputs

```bash
# Count completed output files
ls /scratch/$USER/barnacle/runs/lapidus/ocr/*.jsonl | wc -l

# View sample output
head /scratch/$USER/barnacle/runs/lapidus/ocr/<SHA1>.jsonl
```

## Resource Configuration

### SLURM Resource Requests

Adjust resources in `slurm/process_manifest.sh` or via `sbatch` options:

```bash
#SBATCH --cpus-per-task=4      # CPU cores per task
#SBATCH --mem=16G              # Memory per task
#SBATCH --time=02:00:00        # Max time per task
#SBATCH --partition=batch      # SLURM partition
```

**Recommendations**:
- **CPUs**: 4-8 cores (Kraken can use multiple threads)
- **Memory**: 16GB (sufficient for most manifests, increase for very large images)
- **Time**: 2 hours (adjust based on manifest size and pages)
- **Partition**: Use cluster-specific partition names

### Environment Variables

Set via `--export` or in wrapper script:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `MANIFEST_LIST` | Yes | Path to manifest list file | `manifests.txt` |
| `MODEL_PATH` | Yes | Path to Kraken model | `/project/barnacle/models/model.mlmodel` |
| `CONTAINER` | Yes | Path to Singularity container | `/project/barnacle/barnacle.sif` |
| `CACHE_DIR` | No | Image cache directory | `/scratch/$USER/barnacle/cache` |

## Fault Tolerance

### Resubmit Failed Tasks

If some tasks fail, resubmit only the failed ones:

```bash
# Get list of failed array task IDs
FAILED_TASKS=$(sacct -j <JOB_ID> --format=JobID,State \
    | grep FAILED \
    | awk '{print $1}' \
    | sed 's/.*_//' \
    | tr '\n' ',' \
    | sed 's/,$//')

# Resubmit only failed tasks
sbatch --array=$FAILED_TASKS \
    --export=ALL,MANIFEST_LIST=manifests.txt,MODEL_PATH=/project/barnacle/models/model.mlmodel,CONTAINER=/project/barnacle/barnacle.sif \
    slurm/process_manifest.sh
```

### Resume Within Manifest

If a task is interrupted mid-manifest, the `--resume` flag (enabled by default) will skip already-processed pages:

```bash
# Worker automatically resumes from existing output file
barnacle ocr <MANIFEST_URL> --out result.jsonl --resume
```

### Cancel Jobs

```bash
# Cancel entire job array
scancel <JOB_ID>

# Cancel specific array task
scancel <JOB_ID>_<ARRAY_TASK_ID>

# Cancel all your jobs
scancel -u $USER
```

## Advanced Usage

### GPU Acceleration (Optional)

If cluster has GPUs and Kraken supports GPU acceleration:

```bash
# Request GPU in SLURM script
#SBATCH --gres=gpu:1
#SBATCH --partition=gpu

# Enable NVIDIA GPU in Singularity
singularity exec --nv \
    --bind ... \
    barnacle.sif barnacle ocr ...
```

### Limit Pages for Testing

Test with first few pages before full run:

```bash
# Add --max-pages flag
singularity exec ... barnacle.sif barnacle ocr <MANIFEST_URL> \
    --max-pages 5
```

### Array Task Throttling

Limit concurrent tasks to avoid overloading resources:

```bash
# Run max 100 tasks at once
sbatch --array=1-2778%100 ...
```

### Dependency Chains

Submit jobs that depend on completion of previous jobs:

```bash
# Submit first job
JOB1=$(sbatch ... | awk '{print $4}')

# Submit second job that waits for first
sbatch --dependency=afterok:$JOB1 ...
```

## Storage Patterns

### Recommended Layout

```
/project/barnacle/
├── barnacle.sif                       # Container (read-only)
├── models/
│   └── McCATMuS_nfd_nofix_V1.mlmodel # Model (read-only)

/scratch/$USER/barnacle/
├── cache/
│   └── images/                        # Downloaded images (read-write, shared)
├── runs/
│   ├── lapidus_20260122/
│   │   ├── manifests.txt              # Manifest list
│   │   ├── run_metadata.txt           # Run info
│   │   ├── logs/
│   │   │   ├── barnacle-12345_1.out
│   │   │   ├── barnacle-12345_2.out
│   │   │   └── ...
│   │   └── ocr/
│   │       ├── abc123def456...jsonl   # Per-manifest outputs
│   │       ├── 789ghi012jkl...jsonl
│   │       └── ...
│   └── some_other_collection/
│       └── ...
```

### Cleanup

Periodically clean up scratch space:

```bash
# Remove old cache (images can be re-downloaded)
rm -rf /scratch/$USER/barnacle/cache/images/*

# Archive completed runs
tar czf lapidus_20260122.tar.gz runs/lapidus_20260122/
# Move to long-term storage, delete from scratch
```

## Troubleshooting

### Job Fails Immediately

Check SLURM output logs:

```bash
cat logs/barnacle-<JOB_ID>_1.err
```

Common issues:
- Container not found: Check `CONTAINER` path
- Model not found: Check `MODEL_PATH` path
- Manifest list format: Verify one URL per line

### Singularity Bind Mount Errors

Ensure paths exist and are readable:

```bash
ls -ld /project/barnacle/
ls -ld /scratch/$USER/barnacle/cache/
```

### Out of Memory Errors

Increase memory request:

```bash
sbatch --mem=32G ...
```

### Timeout Errors

Increase time limit:

```bash
sbatch --time=04:00:00 ...
```

Or reduce manifest size with `--max-pages` for testing.

## Performance Tuning

### Batch Size

For very large collections, consider splitting into multiple submissions:

```bash
# Submit first 1000 manifests
sbatch --array=1-1000 ...

# Submit next 1000 after first batch completes
sbatch --array=1001-2000 ...
```

### Cache Sharing

All workers share the same cache directory, reducing redundant downloads for images that appear in multiple manifests.

### Throughput Estimation

Benchmark with small sample:

```bash
# Process 10 manifests
sbatch --array=1-10 ...

# Measure elapsed time from logs
# Extrapolate to full collection
```

## Next Steps

After successful SLURM deployment:

1. **Post-processing**: Aggregate results, compute statistics
2. **Export**: Copy outputs to long-term storage
3. **Monitoring**: Set up automated alerts for failed jobs
4. **Optimization**: Profile performance, adjust resources

See `docs/deployment-plan.md` for full production roadmap.
