#!/usr/bin/env bash

# GNU Parallel Batch Processing for Barnacle OCR Pipeline
#
# Alternative to SLURM for running batch processing on Ubuntu VMs or
# similar environments without HPC job schedulers.
#
# Usage:
#   ./scripts/batch_process.sh \
#       --manifest-list manifests.txt \
#       --model 10.5281/zenodo.14585602 \
#       [--jobs 8] \
#       [--resume] \
#       [--tmux]
#
# Examples:
#   # Basic run with default parallelism
#   ./scripts/batch_process.sh --manifest-list manifests.txt --model 10.5281/zenodo.14585602
#
#   # Resume a previous interrupted run
#   ./scripts/batch_process.sh --manifest-list manifests.txt --model 10.5281/zenodo.14585602 \
#       --resume --joblog batch_20260122_123456.log
#
#   # Run in tmux session for long jobs
#   ./scripts/batch_process.sh --manifest-list manifests.txt --model 10.5281/zenodo.14585602 --tmux

set -euo pipefail

# =============================================================================
# Defaults
# =============================================================================

JOBS=$(( $(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4) / 2 ))
JOBS=$((JOBS > 0 ? JOBS : 1))  # Ensure at least 1 job
RESUME=false
USE_TMUX=false
JOBLOG="batch_$(date +%Y%m%d_%H%M%S).log"
MANIFEST_LIST=""
MODEL=""

# =============================================================================
# Help
# =============================================================================

show_help() {
    cat << 'EOF'
GNU Parallel Batch Processing for Barnacle OCR Pipeline

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

Examples:
  # Basic run
  ./scripts/batch_process.sh \
      --manifest-list manifests.txt \
      --model 10.5281/zenodo.14585602

  # Run with 4 workers
  ./scripts/batch_process.sh \
      --manifest-list manifests.txt \
      --model 10.5281/zenodo.14585602 \
      --jobs 4

  # Resume interrupted batch
  ./scripts/batch_process.sh \
      --manifest-list manifests.txt \
      --model 10.5281/zenodo.14585602 \
      --resume \
      --joblog batch_20260122_123456.log

  # Run in tmux for long jobs
  ./scripts/batch_process.sh \
      --manifest-list manifests.txt \
      --model 10.5281/zenodo.14585602 \
      --tmux

Manifest List Format:
  The manifest list should be a TSV file with two columns:
    <manifest_url><TAB><output_path>

  Generate with scripts/prepare_collection.py:
    python scripts/prepare_collection.py <COLLECTION_URL> \
        --manifest-list manifests.txt \
        --output-dir ./output

See docs/batch-processing.md for detailed documentation.
EOF
}

# =============================================================================
# Parse Arguments
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --manifest-list)
            MANIFEST_LIST="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --jobs)
            JOBS="$2"
            shift 2
            ;;
        --joblog)
            JOBLOG="$2"
            shift 2
            ;;
        --resume)
            RESUME=true
            shift
            ;;
        --tmux)
            USE_TMUX=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Error: Unknown option: $1" >&2
            echo "Use --help for usage information." >&2
            exit 1
            ;;
    esac
done

# =============================================================================
# Validate Required Arguments
# =============================================================================

if [[ -z "$MANIFEST_LIST" ]]; then
    echo "Error: --manifest-list is required" >&2
    echo "Use --help for usage information." >&2
    exit 1
fi

if [[ -z "$MODEL" ]]; then
    echo "Error: --model is required" >&2
    echo "Use --help for usage information." >&2
    exit 1
fi

if [[ ! -f "$MANIFEST_LIST" ]]; then
    echo "Error: Manifest list not found: $MANIFEST_LIST" >&2
    exit 1
fi

# =============================================================================
# Check Prerequisites
# =============================================================================

if ! command -v parallel &> /dev/null; then
    echo "Error: GNU Parallel is not installed." >&2
    echo "" >&2
    echo "Install with:" >&2
    echo "  Ubuntu/Debian: sudo apt install parallel" >&2
    echo "  macOS:         brew install parallel" >&2
    echo "  RHEL/CentOS:   sudo dnf install parallel" >&2
    exit 1
fi

if ! command -v barnacle &> /dev/null; then
    echo "Error: barnacle command not found." >&2
    echo "" >&2
    echo "Install with:" >&2
    echo "  pdm install" >&2
    echo "" >&2
    echo "Or activate your virtual environment first." >&2
    exit 1
fi

# =============================================================================
# Count Manifests
# =============================================================================

MANIFEST_COUNT=$(wc -l < "$MANIFEST_LIST" | tr -d ' ')

if [[ "$MANIFEST_COUNT" -eq 0 ]]; then
    echo "Error: No manifests found in $MANIFEST_LIST" >&2
    exit 1
fi

# =============================================================================
# Build Command
# =============================================================================

# Construct the barnacle command to run for each manifest
# {1} = manifest_url, {2} = output_path (from TSV columns)
BARNACLE_CMD="barnacle ocr {1} --model '$MODEL' --out {2} --resume"

# Build parallel options
PARALLEL_OPTS=(
    "--colsep" "\t"
    "--jobs" "$JOBS"
    "--progress"
    "--joblog" "$JOBLOG"
)

if [[ "$RESUME" == true ]]; then
    if [[ ! -f "$JOBLOG" ]]; then
        echo "Warning: --resume specified but joblog not found: $JOBLOG" >&2
        echo "Starting fresh run instead." >&2
    else
        PARALLEL_OPTS+=("--resume-failed")
        echo "Resuming from joblog: $JOBLOG"
    fi
fi

# =============================================================================
# Display Configuration
# =============================================================================

echo "=========================================="
echo "Barnacle Batch Processing (GNU Parallel)"
echo "=========================================="
echo "Manifest List:  $MANIFEST_LIST"
echo "Manifest Count: $MANIFEST_COUNT"
echo "Model:          $MODEL"
echo "Parallel Jobs:  $JOBS"
echo "Job Log:        $JOBLOG"
echo "Resume Mode:    $RESUME"
echo "=========================================="

# =============================================================================
# Execute
# =============================================================================

if [[ "$USE_TMUX" == true ]]; then
    # Check for tmux
    if ! command -v tmux &> /dev/null; then
        echo "Error: tmux is not installed." >&2
        echo "Install with: sudo apt install tmux" >&2
        exit 1
    fi

    # Check if session already exists
    if tmux has-session -t barnacle 2>/dev/null; then
        echo "Error: tmux session 'barnacle' already exists." >&2
        echo "Attach with: tmux attach -t barnacle" >&2
        echo "Or kill it:  tmux kill-session -t barnacle" >&2
        exit 1
    fi

    # Create script to run in tmux
    TMUX_SCRIPT=$(mktemp)
    cat > "$TMUX_SCRIPT" << TMUXEOF
#!/bin/bash
set -euo pipefail
cd "$(pwd)"
echo "Starting batch processing in tmux session..."
echo "Manifest count: $MANIFEST_COUNT"
echo "Parallel jobs:  $JOBS"
echo ""
cat '$MANIFEST_LIST' | parallel ${PARALLEL_OPTS[@]} '$BARNACLE_CMD'
EXIT_CODE=\$?
echo ""
echo "=========================================="
if [[ \$EXIT_CODE -eq 0 ]]; then
    echo "Batch processing completed successfully!"
else
    echo "Batch processing finished with errors (exit code: \$EXIT_CODE)"
fi
echo "Review results in: $JOBLOG"
echo "=========================================="
echo ""
echo "Press Enter to close this session..."
read
TMUXEOF
    chmod +x "$TMUX_SCRIPT"

    # Start tmux session
    tmux new-session -d -s barnacle "bash $TMUX_SCRIPT; rm -f $TMUX_SCRIPT"

    echo ""
    echo "Started in tmux session 'barnacle'"
    echo ""
    echo "Commands:"
    echo "  tmux attach -t barnacle      # Attach to session"
    echo "  tmux kill-session -t barnacle # Stop processing"
    echo ""
else
    # Run directly with graceful shutdown on Ctrl+C
    echo ""
    echo "Starting batch processing..."
    echo "Press Ctrl+C to stop (current jobs will complete)"
    echo ""

    # Set up signal handler for graceful shutdown
    trap 'echo ""; echo "Interrupted! Waiting for running jobs to complete..."; echo "Progress saved to: $JOBLOG"' INT

    # Run parallel
    set +e  # Don't exit on error so we can report status
    cat "$MANIFEST_LIST" | parallel "${PARALLEL_OPTS[@]}" "$BARNACLE_CMD"
    EXIT_CODE=$?
    set -e

    echo ""
    echo "=========================================="
    if [[ $EXIT_CODE -eq 0 ]]; then
        echo "Batch processing completed successfully!"
    else
        echo "Batch processing finished with errors (exit code: $EXIT_CODE)"
        echo ""
        echo "To resume failed jobs:"
        echo "  $0 --manifest-list $MANIFEST_LIST --model $MODEL --resume --joblog $JOBLOG"
    fi
    echo ""
    echo "Job log: $JOBLOG"
    echo "=========================================="

    exit $EXIT_CODE
fi
