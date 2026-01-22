#!/bin/bash
#SBATCH --job-name=barnacle-ocr
#SBATCH --output=logs/barnacle-%A_%a.out
#SBATCH --error=logs/barnacle-%A_%a.err
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --partition=batch

# SLURM Job Array Script for Barnacle OCR Pipeline
#
# Each array task processes one manifest from the manifest list.
# Usage:
#   sbatch --array=1-N \
#     --export=MANIFEST_LIST=manifests.txt,MODEL_PATH=/models/model.mlmodel \
#     slurm/process_manifest.sh
#
# Required environment variables:
#   MANIFEST_LIST - Path to manifest list file (TSV: manifest_url, output_path)
#   MODEL_PATH    - Path to Kraken model file
#   CONTAINER     - Path to Singularity container (.sif file)
#
# Optional environment variables:
#   CACHE_DIR     - Path to image cache directory (default: /scratch/$USER/barnacle/cache)

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# Required variables (fail if not set)
MANIFEST_LIST="${MANIFEST_LIST:?Error: MANIFEST_LIST not set}"
MODEL_PATH="${MODEL_PATH:?Error: MODEL_PATH not set}"
CONTAINER="${CONTAINER:?Error: CONTAINER not set}"

# Optional variables with defaults
CACHE_DIR="${CACHE_DIR:-/scratch/$USER/barnacle/cache}"

# Validate files exist
if [[ ! -f "$MANIFEST_LIST" ]]; then
    echo "Error: Manifest list not found: $MANIFEST_LIST" >&2
    exit 1
fi

if [[ ! -f "$MODEL_PATH" ]]; then
    echo "Error: Model file not found: $MODEL_PATH" >&2
    exit 1
fi

if [[ ! -f "$CONTAINER" ]]; then
    echo "Error: Container not found: $CONTAINER" >&2
    exit 1
fi

# =============================================================================
# Get Manifest Info for This Array Task
# =============================================================================

# Extract line for this array task
LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MANIFEST_LIST")

if [[ -z "$LINE" ]]; then
    echo "Error: No manifest found for array task ID $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

# Parse TSV: manifest_url <TAB> output_path
MANIFEST_URL=$(echo "$LINE" | cut -f1)
OUTPUT_PATH=$(echo "$LINE" | cut -f2)

# =============================================================================
# Log Job Info
# =============================================================================

echo "=========================================="
echo "Barnacle OCR Pipeline"
echo "=========================================="
echo "SLURM Job ID:        $SLURM_ARRAY_JOB_ID"
echo "SLURM Array Task ID: $SLURM_ARRAY_TASK_ID"
echo "Hostname:            $(hostname)"
echo "Start Time:          $(date)"
echo "=========================================="
echo "Manifest URL:        $MANIFEST_URL"
echo "Output Path:         $OUTPUT_PATH"
echo "Model:               $MODEL_PATH"
echo "Cache Directory:     $CACHE_DIR"
echo "Container:           $CONTAINER"
echo "=========================================="

# =============================================================================
# Prepare Directories
# =============================================================================

# Ensure cache directory exists
mkdir -p "$CACHE_DIR"

# Ensure output directory exists
OUTPUT_DIR=$(dirname "$OUTPUT_PATH")
mkdir -p "$OUTPUT_DIR"

# =============================================================================
# Run Barnacle via Singularity
# =============================================================================

echo "Starting OCR processing..."

singularity exec \
  --bind "$(dirname "$MODEL_PATH"):/models:ro" \
  --bind "$CACHE_DIR:/cache" \
  --bind "$OUTPUT_DIR:/output" \
  "$CONTAINER" \
  barnacle ocr "$MANIFEST_URL" \
    --model "/models/$(basename "$MODEL_PATH")" \
    --cache-dir /cache \
    --out "/output/$(basename "$OUTPUT_PATH")" \
    --resume \
    --log-level INFO

EXIT_CODE=$?

# =============================================================================
# Report Results
# =============================================================================

echo "=========================================="
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "✅ SUCCESS"
    echo "Manifest:  $MANIFEST_URL"
    echo "Output:    $OUTPUT_PATH"
    echo "End Time:  $(date)"
else
    echo "❌ FAILED (exit code: $EXIT_CODE)"
    echo "Manifest:  $MANIFEST_URL"
    echo "Output:    $OUTPUT_PATH"
    echo "End Time:  $(date)"
fi
echo "=========================================="

exit $EXIT_CODE
