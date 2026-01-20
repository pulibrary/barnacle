# Barnacle Production Deployment Plan

**Project**: Barnacle OCR Pipeline
**Target**: Tufts HPC Cluster (SLURM)
**Date**: January 2026
**Status**: Planning Phase

---

## Executive Summary

This document outlines the plan for deploying Barnacle, a high-quality OCR pipeline for historical documents, on the Tufts HPC cluster. The deployment will enable parallel processing of thousands of IIIF manifests using SLURM job arrays and containerized execution.

### Key Goals

1. **Containerize application** for reproducible, portable deployment
2. **Support parallel manifest processing** across cluster nodes
3. **Integrate with SLURM** job scheduling for scalable batch processing
4. **Refactor code** to support production patterns (proper abstractions, type safety)
5. **Enable Collection handling** with per-manifest output files and resume safety

### Expected Scale

- **Target collection**: Lapidus (~2,778 titles)
- **Estimated pages**: ~500,000+ pages total
- **Processing time**: ~1 minute/page (without cache), seconds with cache
- **Parallelism**: 50-100 concurrent SLURM jobs (configurable)

---

## Deployment Environment

### Tufts HPC Cluster Specifications

Based on [Tufts HPC Documentation](https://rtguides.it.tufts.edu/hpc/index.html):

- **Scheduler**: SLURM
- **Network**: 100Gbps ethernet interconnect (excellent for distributed processing)
- **GPU Resources**: Available (may improve Kraken OCR performance)
- **Container Support**: TBD - likely Singularity/Apptainer (HPC standard)
- **Storage**: TBD - consult cluster managers
- **Contact**: tts-research@tufts.edu

### Current Unknowns (Require Cluster Manager Input)

❓ **Container runtime**: Singularity version? Apptainer? Docker support?
❓ **Storage paths**: Where to store cache, outputs, models?
❓ **Resource limits**: Max array size? Job duration limits? Memory per node?
❓ **Partitions**: Which SLURM partitions for CPU/GPU jobs?
❓ **Network**: Any HTTP/HTTPS egress restrictions for fetching IIIF manifests?

---

## Architecture Overview

### Deployment Pattern: SLURM Job Array

**Recommended approach**: Use SLURM job arrays for embarrassingly parallel manifest processing.

```
Input: IIIF Collection or manifest list (CSV)
  ↓
Coordinator (login node):
  - Parse collection
  - Generate manifest list (one line per manifest)
  - Create output directory structure
  ↓
SLURM Job Array Submission:
  - Array size: N manifests
  - Each task processes 1 manifest
  ↓
Parallel Execution (compute nodes):
  ├─ Task 1: Manifest 1 → SHA1-named JSONL
  ├─ Task 2: Manifest 2 → SHA1-named JSONL
  ├─ Task 3: Manifest 3 → SHA1-named JSONL
  ...
  └─ Task N: Manifest N → SHA1-named JSONL
  ↓
Output: Shared filesystem
  - runs/<run_name>/ocr/<sha1_manifest1>.jsonl
  - runs/<run_name>/ocr/<sha1_manifest2>.jsonl
  - ...
  - runs/<run_name>/metadata.json (run summary)
```

### Key Benefits

✅ **SLURM-native parallelism** - No external orchestration needed
✅ **Per-manifest isolation** - Each job writes to a different file
✅ **Resume safety** - Failed jobs can be resubmitted individually
✅ **Fault tolerance** - Job failures don't affect other manifests
✅ **Scalability** - Easily process thousands of manifests in parallel

### Alternative Architectures (For Discussion)

**Option B: Workflow Manager** (Snakemake/Nextflow)
- Pros: Dependency tracking, complex pipelines
- Cons: Additional complexity, learning curve

**Option C: MPI-based** (single large job with MPI ranks)
- Pros: Tightly coupled, efficient inter-process communication
- Cons: Less fault-tolerant, all-or-nothing execution

**Recommendation**: Start with Option A (job arrays) for simplicity and fault tolerance.

---

## Implementation Phases

### Phase 1: Code Refactoring (Weeks 1-2)

**Goal**: Modular codebase ready for production deployment

#### 1.1 Create IIIF Models Module

**New module**: `src/barnacle/iiif/v2/`

Create Pydantic models for IIIF Presentation 2.1 resources:
- `Manifest` - with `canvases()` traversal method
- `Collection` - with `manifest_ids()` extractor
- `Canvas` - with `image_url()` for IIIF Image API
- `ImageService` - IIIF Image API service descriptor
- Loaders, validation, and traversal helpers

**Benefits**:
- Type safety (Pydantic validation catches errors early)
- Clean abstraction layer (easier to test and maintain)
- Serializable (can pass models between processes if needed)

#### 1.2 Extract Pipeline Module

**New module**: `src/barnacle/pipeline/`

Separate pipeline logic from CLI for programmatic use:
- `coordinator.py` - Parse collections, generate manifest lists
- `worker.py` - Process single manifest (core processing function)
- `output.py` - Output path resolution, resume tracking
- `batch.py` - Batch processing utilities

**Key function signatures**:

```python
# coordinator.py
def prepare_manifest_list(
    collection_or_manifest: str,
    output_dir: Path,
) -> list[ManifestTask]:
    """Parse and generate task list for SLURM."""

# worker.py
def process_manifest(
    manifest_id: str,
    output_path: Path,
    *,
    model: str,
    cache_dir: Path,
    max_pages: int | None = None,
    resume: bool = True,
) -> ProcessingResult:
    """Process single manifest (SLURM worker function)."""
```

**Benefits**:
- CLI becomes thin wrapper
- SLURM scripts can import pipeline modules directly
- Testable without CLI framework
- Reusable for future deployment patterns

#### 1.3 Add New CLI Commands

Update CLI to use new modules:
- `barnacle ocr` - Existing, but refactored to use pipeline modules
- `barnacle validate` - Existing, updated to use Pydantic models
- `barnacle prepare` - **NEW**: Generate manifest list from collection

**Example usage**:
```bash
# Generate manifest list for SLURM
barnacle prepare <COLLECTION_URL> \
  --output-dir runs/lapidus_batch \
  --manifest-list manifests.txt

# Output:
#  manifests.txt (tab-separated: manifest_url, output_path)
#  runs/lapidus_batch/ocr/ (empty directory)
```

#### Deliverables

- [ ] IIIF models module with tests
- [ ] Pipeline module with tests
- [ ] Updated CLI commands
- [ ] Documentation of new APIs

---

### Phase 2: Containerization (Week 3)

**Goal**: Reproducible, portable container images for HPC deployment

#### 2.1 Container Strategy

HPC clusters typically use **Singularity** or **Apptainer** (not Docker) for security in multi-tenant environments.

**Build strategy**:
1. Create Dockerfile (for development, local testing, CI)
2. Build Docker image
3. Convert to Singularity/Apptainer for HPC

#### 2.2 Dockerfile

**File**: `Dockerfile`

```dockerfile
FROM python:3.12-slim

# System dependencies for Kraken
RUN apt-get update && apt-get install -y \
    git \
    libvips-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml pdm.lock README.md ./
COPY src/ ./src/

# Install dependencies
RUN pip install --no-cache-dir pdm && \
    pdm install --prod --no-editable

# Create mount points
RUN mkdir -p /models /cache /output

# Entry point
ENTRYPOINT ["pdm", "run", "barnacle"]
CMD ["--help"]
```

**Build**:
```bash
docker build -t barnacle:latest .
docker tag barnacle:latest barnacle:$(git rev-parse --short HEAD)
```

#### 2.3 Singularity Definition

**File**: `barnacle.def`

```singularity
Bootstrap: docker
From: python:3.12-slim

%files
    pyproject.toml /app/
    pdm.lock /app/
    README.md /app/
    src/ /app/src/

%post
    apt-get update && apt-get install -y git libvips-dev
    apt-get clean
    cd /app
    pip install pdm
    pdm install --prod --no-editable

%environment
    export PATH=/app/.venv/bin:$PATH

%runscript
    exec barnacle "$@"
```

**Build on HPC**:
```bash
# Convert from Docker
docker save barnacle:latest | \
  singularity build barnacle.sif docker-archive:/dev/stdin

# Or build directly
singularity build barnacle.sif barnacle.def
```

#### 2.4 Container Testing

**Test locally (Docker)**:
```bash
docker run --rm \
  -v $(pwd)/models:/models \
  -v $(pwd)/cache:/cache \
  -v $(pwd)/output:/output \
  barnacle:latest ocr <MANIFEST_URL> \
    --model /models/model.mlmodel \
    --cache-dir /cache \
    --out /output/test.jsonl \
    --max-pages 5
```

**Test on HPC (Singularity)**:
```bash
singularity exec \
  --bind /path/to/models:/models:ro \
  --bind /scratch/$USER/cache:/cache \
  --bind /scratch/$USER/output:/output \
  barnacle.sif \
  barnacle ocr <MANIFEST_URL> \
    --model /models/model.mlmodel \
    --cache-dir /cache \
    --out /output/test.jsonl \
    --max-pages 5
```

#### Deliverables

- [ ] Dockerfile and build scripts
- [ ] Singularity definition file
- [ ] Tested container on HPC login node
- [ ] Container build documentation

---

### Phase 3: SLURM Integration (Week 4)

**Goal**: Working SLURM job array for parallel processing

#### 3.1 Manifest Preparation Script

**File**: `scripts/prepare_collection.py`

```python
#!/usr/bin/env python3
"""Prepare collection for SLURM job array."""
from pathlib import Path
import typer
from barnacle.pipeline.coordinator import prepare_manifest_list

app = typer.Typer()

@app.command()
def main(
    collection_or_manifest: str,
    manifest_list: Path = typer.Option(...),
    output_dir: Path = typer.Option(...),
):
    """Generate manifest list for SLURM job array."""
    output_dir.mkdir(parents=True, exist_ok=True)
    tasks = prepare_manifest_list(collection_or_manifest, output_dir)

    with manifest_list.open("w") as f:
        for task in tasks:
            f.write(f"{task.manifest_id}\t{task.output_path}\n")

    print(f"✅ Prepared {len(tasks)} manifests")
    print(f"   List: {manifest_list}")
    print(f"   Output: {output_dir}")

if __name__ == "__main__":
    app()
```

#### 3.2 SLURM Job Script

**File**: `slurm/process_manifest.sh`

```bash
#!/bin/bash
#SBATCH --job-name=barnacle-ocr
#SBATCH --output=logs/barnacle-%A_%a.out
#SBATCH --error=logs/barnacle-%A_%a.err
#SBATCH --array=1-N
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --partition=batch

# Configuration
MANIFEST_LIST="${MANIFEST_LIST:-manifests.txt}"
MODEL_PATH="${MODEL_PATH:-/models/model.mlmodel}"
CACHE_DIR="${CACHE_DIR:-/scratch/$USER/barnacle/cache}"
CONTAINER="${CONTAINER:-barnacle.sif}"

# Get manifest for this array task
LINE=$(sed -n "${SLURM_ARRAY_TASK_ID}p" "$MANIFEST_LIST")
MANIFEST_URL=$(echo "$LINE" | cut -f1)
OUTPUT_PATH=$(echo "$LINE" | cut -f2)

echo "Task $SLURM_ARRAY_TASK_ID: $MANIFEST_URL"

# Run Barnacle
singularity exec \
  --bind $(dirname $MODEL_PATH):/models:ro \
  --bind $CACHE_DIR:/cache \
  --bind $(dirname $OUTPUT_PATH):/output \
  "$CONTAINER" \
  barnacle ocr "$MANIFEST_URL" \
    --model /models/$(basename $MODEL_PATH) \
    --cache-dir /cache \
    --out /output/$(basename $OUTPUT_PATH) \
    --resume \
    --log-level INFO

if [ $? -eq 0 ]; then
    echo "✅ Success: $MANIFEST_URL"
else
    echo "❌ Failed: $MANIFEST_URL"
    exit 1
fi
```

#### 3.3 End-to-End Wrapper

**File**: `slurm/run_collection.sh`

```bash
#!/bin/bash
set -euo pipefail

COLLECTION_URL="$1"
RUN_NAME="${2:-$(date +%Y%m%d_%H%M%S)}"
RUN_DIR="/scratch/$USER/barnacle/runs/$RUN_NAME"

mkdir -p "$RUN_DIR/ocr" "$RUN_DIR/logs"

echo "Barnacle Collection Processing"
echo "Collection: $COLLECTION_URL"
echo "Run: $RUN_DIR"

# Prepare manifest list
python scripts/prepare_collection.py \
  "$COLLECTION_URL" \
  --manifest-list "$RUN_DIR/manifests.txt" \
  --output-dir "$RUN_DIR/ocr"

N=$(wc -l < "$RUN_DIR/manifests.txt")
echo "✅ $N manifests prepared"

# Submit job array
JOB_ID=$(sbatch \
  --array=1-$N \
  --output="$RUN_DIR/logs/barnacle-%A_%a.out" \
  --error="$RUN_DIR/logs/barnacle-%A_%a.err" \
  --export=MANIFEST_LIST="$RUN_DIR/manifests.txt" \
  slurm/process_manifest.sh | awk '{print $4}')

echo "✅ Submitted job: $JOB_ID"
echo "   Monitor: squeue -j $JOB_ID"
echo "   Logs: $RUN_DIR/logs/"
```

**Usage**:
```bash
./slurm/run_collection.sh https://dpul.princeton.edu/lapidus lapidus_full
```

#### Deliverables

- [ ] Manifest preparation script
- [ ] SLURM job script
- [ ] End-to-end wrapper
- [ ] Test run with 10-20 manifests
- [ ] Verify resume functionality

---

### Phase 4: Production Features (Week 5)

**Goal**: Production-ready system with monitoring and fault tolerance

#### 4.1 Monitoring & Observability

**SLURM monitoring commands**:
```bash
# Job status
squeue -u $USER

# Specific job
squeue -j <JOB_ID>

# Failed tasks
sacct -j <JOB_ID> --format=JobID,State,ExitCode | grep FAILED
```

**Post-processing summary script**: `scripts/summarize_run.py`

Parse SLURM logs and JSONL outputs to generate:
- Total manifests processed
- Total pages processed
- Processing throughput (pages/hour)
- Failed manifests (list for retry)
- Timing statistics

#### 4.2 Fault Tolerance

**Resume capabilities**:
1. **Page-level resume** (already implemented): `--resume` skips processed pages
2. **Manifest-level resume** (new): Resubmit only failed array tasks

**Resubmit failed jobs**:
```bash
# Get failed task IDs
FAILED=$(sacct -j $JOB_ID --format=JobID,State,ExitCode | \
  grep FAILED | awk '{print $1}' | sed 's/.*_//' | tr '\n' ',')

# Resubmit
sbatch --array=$FAILED slurm/process_manifest.sh
```

#### 4.3 Provenance Tracking

**Run metadata** (`runs/<name>/metadata.json`):
```json
{
  "run_name": "lapidus_full",
  "collection_url": "https://dpul.princeton.edu/lapidus",
  "start_time": "2026-01-20T10:00:00Z",
  "end_time": "2026-01-20T18:30:00Z",
  "slurm_job_id": "12345",
  "container": "barnacle.sif",
  "container_sha256": "abc123...",
  "git_commit": "def456...",
  "model": {
    "doi": "10.5281/zenodo.14585602",
    "path": "/models/model.mlmodel"
  },
  "manifest_count": 2778,
  "total_pages": 456789,
  "elapsed_hours": 8.5
}
```

**Output JSONL includes**:
- Git commit SHA
- Container image ID
- Model version/DOI
- SLURM job and task IDs
- Processing timestamp

#### 4.4 Optional: GPU Support

If GPUs improve Kraken performance:

**SLURM job**:
```bash
#SBATCH --gres=gpu:1
#SBATCH --partition=gpu
```

**Singularity**:
```bash
singularity exec --nv barnacle.sif barnacle ocr ...
```

**Action**: Benchmark Kraken with/without GPU to determine benefit.

#### Deliverables

- [ ] Monitoring scripts
- [ ] Run summarization tool
- [ ] Provenance tracking
- [ ] Fault tolerance testing
- [ ] User documentation

---

## Storage Strategy

### Recommended: Shared Filesystem (Option A)

**Pattern**:
- **Inputs**: IIIF manifests (HTTP, no local storage)
- **Cache**: `/scratch/$USER/barnacle/cache/` (shared across jobs)
- **Outputs**: `/scratch/$USER/barnacle/runs/<name>/ocr/` (per-manifest files)
- **Models**: `/project/barnacle/models/` or bind mount (read-only)

**Benefits**:
- Standard HPC pattern
- Cache deduplication (all nodes share cache)
- No file write contention (each job writes different files)
- Simple implementation

**Questions for cluster managers**:
1. Where should cache be stored? Purge policy?
2. Where should outputs go? Quota limits?
3. Is there a shared model directory?
4. Best practices for shared scratch space?

### Alternative: Object Storage (Option B)

**Pattern**:
- Cache on local node (ephemeral)
- Upload outputs to S3/MinIO after processing
- Download model from S3 or bake into container

**Benefits**: Cloud-native, long-term storage integrated
**Drawbacks**: S3 required, no cache sharing, credential management

### Alternative: Hybrid (Option C)

Process on shared filesystem, then export to external storage in post-processing step.

---

## Success Criteria

### Stage 1: Code Refactoring
- [x] IIIF models parse real Figgy manifests
- [x] Pipeline modules are testable and documented
- [x] CLI commands use new modules
- [x] Tests pass

### Stage 2: Containerization
- [x] Docker image builds successfully
- [x] Singularity image runs on HPC
- [x] Container can fetch manifests and run OCR
- [x] Build process is documented

### Stage 3: SLURM Integration
- [x] Manifest preparation script works
- [x] SLURM job array processes manifests in parallel
- [x] Per-manifest output files created correctly
- [x] Resume functionality works

### Stage 4: Production
- [x] Monitoring scripts provide useful metrics
- [x] Failed jobs can be resubmitted
- [x] Provenance tracking is complete
- [x] Documentation enables deployment by cluster managers

### Overall Success
- ✅ Collections processed in parallel at scale
- ✅ Per-manifest resume safety
- ✅ Container deployment is reproducible
- ✅ SLURM integration is production-ready
- ✅ System handles failures gracefully

---

## Questions for Cluster Managers

Before proceeding with implementation, we need answers to:

### 1. Container Runtime
- Which container system? (Singularity, Apptainer, version?)
- Any specific requirements or best practices?
- Build restrictions (e.g., must build on specific node)?

### 2. Storage
- **Cache**: Where should temporary image downloads go?
  - `/scratch/$USER/`? `/tmp/`? Other?
  - Purge policy? Quota?
- **Outputs**: Where should JSONL outputs be stored?
  - `/scratch/`? `/project/`?
  - How long until archival/cleanup?
- **Models**: Is there a shared model directory? Or mount at runtime?
- **Disk quotas**: Limits per user/project?

### 3. SLURM Configuration
- **Partitions**: Which partition(s) for CPU jobs? GPU jobs?
- **Resource limits**:
  - Max job array size?
  - Max job duration?
  - Memory per node?
  - Max concurrent jobs per user?
- **Batch vs interactive**: Any guidelines?

### 4. Network
- HTTP/HTTPS egress allowed for fetching IIIF manifests?
- Any proxy configuration needed?
- Rate limiting considerations?

### 5. Best Practices
- Cluster-specific guidelines for containerized jobs?
- Preferred logging/monitoring approaches?
- Data management policies (how long to keep outputs)?

---

## Timeline

### Week 1-2: Code Refactoring
- Create IIIF models module
- Extract pipeline module
- Update CLI
- Write tests

### Week 3: Containerization
- Write Dockerfile
- Build and test Docker image
- Convert to Singularity
- Test on HPC

### Week 4: SLURM Integration
- Write SLURM scripts
- Test with small collection
- Verify parallel processing
- Document submission process

### Week 5: Production Hardening
- Add monitoring
- Test fault tolerance
- Performance benchmarking
- Final documentation

**Target completion**: End of Week 5 (~5 weeks from start)

---

## Contact & Resources

**Development Team**: Princeton University Library
**Target Cluster**: Tufts HPC
**Cluster Support**: tts-research@tufts.edu
**Documentation**: https://rtguides.it.tufts.edu/hpc/

**Project Repository**: https://github.com/pulibrary/barnacle
**IIIF Collection**: https://dpul.princeton.edu/lapidus

---

## Appendix: Technical Details

### Current Barnacle Capabilities

- ✅ IIIF Presentation 2.1 manifest parsing
- ✅ Kraken OCR integration with configurable models
- ✅ Page-level resume functionality
- ✅ Image caching
- ✅ Structured JSON logging
- ✅ Per-page provenance tracking

### Kraken OCR Engine

- **Model**: McCATMuS_nfd_nofix_V1 (historical typography)
- **Input**: IIIF Image API URLs
- **Output**: Plain text per page
- **Performance**: ~1 min/page (first run), <10sec cached
- **GPU**: Untested, may improve performance

### Output Format (JSONL)

Each line is a JSON object:
```json
{
  "manifest_url": "https://...",
  "canvas_id": "https://...",
  "canvas_index": 0,
  "image_url": "https://iiif.../full/!3000,3000/0/default.jpg",
  "text": "Recognized text...",
  "engine": "kraken",
  "model": {"ref": "...", "resolved": "..."},
  "elapsed_ms": 21246,
  "page_key": "...",
  "created_at": "2026-01-20T15:50:07Z"
}
```

### Estimated Resource Requirements (per job)

- **CPU**: 4 cores
- **Memory**: 16GB
- **Disk**: 1GB cache per manifest (images)
- **Network**: ~50MB per manifest (image downloads)
- **Time**: 30min - 2hr per manifest (depending on page count)
