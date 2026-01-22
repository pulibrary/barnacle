#!/bin/bash

# End-to-end script for processing IIIF Collections with Barnacle
#
# This script orchestrates the complete workflow:
# 1. Parse collection and generate manifest list
# 2. Submit SLURM job array to process manifests in parallel
# 3. Monitor job progress
#
# Usage:
#   ./slurm/run_collection.sh <COLLECTION_URL> [RUN_NAME]
#
# Example:
#   ./slurm/run_collection.sh \
#     https://example.org/collection/lapidus \
#     lapidus_batch_20260122

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# Required: Collection URL
if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <COLLECTION_URL> [RUN_NAME]" >&2
    echo "" >&2
    echo "Example:" >&2
    echo "  $0 https://example.org/collection/123 lapidus_batch" >&2
    exit 1
fi

COLLECTION_URL="$1"
RUN_NAME="${2:-$(date +%Y%m%d_%H%M%S)}"

# Paths (customize these for your cluster environment)
BASE_DIR="${BASE_DIR:-/scratch/$USER/barnacle}"
RUN_DIR="$BASE_DIR/runs/$RUN_NAME"
MANIFEST_LIST="$RUN_DIR/manifests.txt"
OUTPUT_DIR="$RUN_DIR/ocr"
LOG_DIR="$RUN_DIR/logs"

# Container and model paths (customize for your environment)
CONTAINER="${CONTAINER:-/project/barnacle/barnacle.sif}"
MODEL_PATH="${MODEL_PATH:-/project/barnacle/models/McCATMuS_nfd_nofix_V1.mlmodel}"
CACHE_DIR="${CACHE_DIR:-$BASE_DIR/cache}"

# SLURM settings (customize for your cluster)
SLURM_PARTITION="${SLURM_PARTITION:-batch}"
SLURM_CPUS="${SLURM_CPUS:-4}"
SLURM_MEM="${SLURM_MEM:-16G}"
SLURM_TIME="${SLURM_TIME:-02:00:00}"

# =============================================================================
# Validate Prerequisites
# =============================================================================

if [[ ! -f "$CONTAINER" ]]; then
    echo "Error: Container not found: $CONTAINER" >&2
    echo "Set CONTAINER environment variable or update script" >&2
    exit 1
fi

if [[ ! -f "$MODEL_PATH" ]]; then
    echo "Error: Model not found: $MODEL_PATH" >&2
    echo "Set MODEL_PATH environment variable or update script" >&2
    exit 1
fi

if ! command -v sbatch &> /dev/null; then
    echo "Error: sbatch command not found. Are you on the SLURM cluster?" >&2
    exit 1
fi

# =============================================================================
# Create Run Directory Structure
# =============================================================================

mkdir -p "$RUN_DIR" "$OUTPUT_DIR" "$LOG_DIR" "$CACHE_DIR"

echo "=========================================="
echo "Barnacle Collection Processing"
echo "=========================================="
echo "Collection:    $COLLECTION_URL"
echo "Run Name:      $RUN_NAME"
echo "Run Directory: $RUN_DIR"
echo "Container:     $CONTAINER"
echo "Model:         $MODEL_PATH"
echo "Cache:         $CACHE_DIR"
echo "=========================================="

# =============================================================================
# Step 1: Prepare Manifest List
# =============================================================================

echo ""
echo "Step 1: Preparing manifest list..."
echo ""

python scripts/prepare_collection.py \
    "$COLLECTION_URL" \
    --manifest-list "$MANIFEST_LIST" \
    --output-dir "$OUTPUT_DIR"

# Count manifests
MANIFEST_COUNT=$(wc -l < "$MANIFEST_LIST")

if [[ $MANIFEST_COUNT -eq 0 ]]; then
    echo "Error: No manifests found in collection" >&2
    exit 1
fi

echo ""
echo "✅ Prepared $MANIFEST_COUNT manifests"

# =============================================================================
# Step 2: Submit SLURM Job Array
# =============================================================================

echo ""
echo "Step 2: Submitting SLURM job array..."
echo ""

JOB_OUTPUT=$(sbatch \
    --array="1-${MANIFEST_COUNT}" \
    --partition="$SLURM_PARTITION" \
    --cpus-per-task="$SLURM_CPUS" \
    --mem="$SLURM_MEM" \
    --time="$SLURM_TIME" \
    --output="$LOG_DIR/barnacle-%A_%a.out" \
    --error="$LOG_DIR/barnacle-%A_%a.err" \
    --export=ALL,MANIFEST_LIST="$MANIFEST_LIST",MODEL_PATH="$MODEL_PATH",CONTAINER="$CONTAINER",CACHE_DIR="$CACHE_DIR" \
    slurm/process_manifest.sh)

JOB_ID=$(echo "$JOB_OUTPUT" | awk '{print $4}')

# Save run metadata
cat > "$RUN_DIR/run_metadata.txt" <<EOF
Collection URL: $COLLECTION_URL
Run Name: $RUN_NAME
Start Time: $(date)
SLURM Job ID: $JOB_ID
Manifest Count: $MANIFEST_COUNT
Container: $CONTAINER
Model: $MODEL_PATH
Cache Directory: $CACHE_DIR
Output Directory: $OUTPUT_DIR
Log Directory: $LOG_DIR
EOF

# =============================================================================
# Report Submission
# =============================================================================

echo ""
echo "=========================================="
echo "✅ SLURM Job Array Submitted"
echo "=========================================="
echo "Job ID:        $JOB_ID"
echo "Array Tasks:   1-$MANIFEST_COUNT"
echo "Partition:     $SLURM_PARTITION"
echo "Resources:     $SLURM_CPUS CPUs, $SLURM_MEM memory"
echo "Time Limit:    $SLURM_TIME"
echo ""
echo "Monitoring Commands:"
echo "  squeue -j $JOB_ID                    # Check job status"
echo "  squeue -j $JOB_ID -t RUNNING        # Running tasks"
echo "  squeue -j $JOB_ID -t PENDING        # Pending tasks"
echo "  sacct -j $JOB_ID --format=JobID,State,ExitCode  # Completed tasks"
echo ""
echo "Logs:"
echo "  ls $LOG_DIR/"
echo "  tail -f $LOG_DIR/barnacle-${JOB_ID}_1.out"
echo ""
echo "Outputs:"
echo "  ls $OUTPUT_DIR/"
echo ""
echo "Cancel Job:"
echo "  scancel $JOB_ID"
echo "=========================================="

# =============================================================================
# Optional: Wait for Completion
# =============================================================================

if [[ "${WAIT:-false}" == "true" ]]; then
    echo ""
    echo "Waiting for job completion (WAIT=true)..."
    echo "Press Ctrl+C to stop waiting (job will continue running)"
    echo ""

    while squeue -j "$JOB_ID" 2>/dev/null | grep -q "$JOB_ID"; do
        RUNNING=$(squeue -j "$JOB_ID" -t RUNNING -h | wc -l)
        PENDING=$(squeue -j "$JOB_ID" -t PENDING -h | wc -l)
        echo "[$(date +%H:%M:%S)] Running: $RUNNING, Pending: $PENDING, Total: $MANIFEST_COUNT"
        sleep 30
    done

    echo ""
    echo "✅ Job array completed"
    echo ""
    echo "Check results:"
    echo "  sacct -j $JOB_ID --format=JobID,State,ExitCode | grep FAILED"
    echo "  ls $OUTPUT_DIR/*.jsonl | wc -l"
fi
