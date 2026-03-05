#!/bin/bash
#SBATCH --job-name=barnacle-ocr
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --partition=batch
#SBATCH --mail-type=FAIL

# SLURM Job Array Worker Script (module-based)
#
# Processes one manifest per array task using the barnacle environment module.
# Submit via run_collection_module.sh or directly with sbatch --array.
#
# Required environment variables (passed via --export):
#   MANIFEST_LIST  - Path to manifest list file (one URL per line)
#   OUTPUT_DIR     - Directory for output JSONL files
#
# Optional environment variables:
#   MODEL          - Kraken model ref: DOI, installed name, or filesystem path
#                    (default: 10.5281/zenodo.10592716, the CATMuS Print Fondue Large model)
#                    Pre-install on the login node before submitting:
#                      barnacle ocr --help  # or: kraken get 10.5281/zenodo.10592716
#   CACHE_BASE     - Base path for image cache (default: /scratch/$USER/barnacle/cache)
#
# Example direct submission:
#   N=$(wc -l < manifests.txt)
#   sbatch --array=1-${N}%50 \
#     --output=logs/barnacle-%A_%a.out \
#     --error=logs/barnacle-%A_%a.err \
#     --export=ALL,MANIFEST_LIST=$PWD/manifests.txt,OUTPUT_DIR=$PWD/output,MODEL=10.5281/zenodo.10592716 \
#     slurm/process_manifest_module.sh

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

MANIFEST_LIST="${MANIFEST_LIST:?Error: MANIFEST_LIST not set}"
OUTPUT_DIR="${OUTPUT_DIR:?Error: OUTPUT_DIR not set}"
MODEL="${MODEL:-10.5281/zenodo.10592716}"
OCR_TIMEOUT="${OCR_TIMEOUT:-120}"

# Per-task cache dir avoids conflicts between simultaneous array tasks
CACHE_BASE="${CACHE_BASE:-/scratch/$USER/barnacle/cache}"
CACHE_DIR="${CACHE_BASE}/${SLURM_ARRAY_TASK_ID}"

# =============================================================================
# Get this task's manifest URL
# =============================================================================

MANIFEST_URL=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MANIFEST_LIST")

if [[ -z "$MANIFEST_URL" ]]; then
    echo "Error: No manifest found for array task ID $SLURM_ARRAY_TASK_ID" >&2
    exit 1
fi

SHA1_HASH=$(echo -n "$MANIFEST_URL" | sha1sum | cut -d' ' -f1)
OUTPUT_PATH="${OUTPUT_DIR}/${SHA1_HASH}.jsonl"

# =============================================================================
# Log job info
# =============================================================================

echo "=========================================="
echo "Barnacle OCR Pipeline (module)"
echo "=========================================="
echo "SLURM Job ID:        ${SLURM_ARRAY_JOB_ID:-unknown}"
echo "SLURM Array Task ID: $SLURM_ARRAY_TASK_ID"
echo "Hostname:            $(hostname)"
echo "Start Time:          $(date)"
echo "=========================================="
echo "Manifest URL:        $MANIFEST_URL"
echo "Output Path:         $OUTPUT_PATH"
echo "Model:               $MODEL"
echo "OCR Timeout:         ${OCR_TIMEOUT}s"
echo "Cache Directory:     $CACHE_DIR"
echo "=========================================="

# =============================================================================
# Prepare directories and load environment
# =============================================================================

mkdir -p "$CACHE_DIR" "$OUTPUT_DIR"

module load use.own
module load barnacle/latest

# =============================================================================
# Run barnacle
# =============================================================================

echo "Starting OCR processing..."

barnacle ocr "$MANIFEST_URL" \
  --model "$MODEL" \
  --cache-dir "$CACHE_DIR" \
  --out "$OUTPUT_PATH" \
  --resume \
  --clear-cache-after \
  --log-level INFO \
  --ocr-timeout "$OCR_TIMEOUT"

EXIT_CODE=$?

# =============================================================================
# Report results
# =============================================================================

echo "=========================================="
if [[ $EXIT_CODE -eq 0 ]]; then
    echo "SUCCESS"
    echo "Manifest:  $MANIFEST_URL"
    echo "Output:    $OUTPUT_PATH"
else
    echo "FAILED (exit code: $EXIT_CODE)"
    echo "Manifest:  $MANIFEST_URL"
    echo "Output:    $OUTPUT_PATH"
fi
echo "End Time: $(date)"
echo "=========================================="

exit $EXIT_CODE
