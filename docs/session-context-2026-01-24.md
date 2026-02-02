# Session Context: Barnacle Production Deployment (2026-01-24)

## Executive Summary

Completed transformation from MVP proof-of-concept to **production-ready HPC deployment system**. The pipeline is now fully containerized with SLURM integration, comprehensive tests, and complete documentation.

**Current Status**: Ready for DockerHub push and HPC testing

---

## What We Accomplished (6 Commits)

### Commit 10b4d27: Add IIIF models and pipeline modules for HPC deployment
**Date**: Jan 21, 2026

**Created modular architecture:**
- `src/barnacle/iiif/v2/` - Type-safe IIIF Presentation 2.1 support
  - `models.py`: Pydantic models (Manifest, Collection, Canvas, ImageService)
  - `loaders.py`: Load JSON from files/URLs, parse into models
  - `validation.py`: Validate for pipeline requirements
  - `traversal.py`: `iter_manifests()` for collection handling

- `src/barnacle/pipeline/` - Processing logic
  - `coordinator.py`: Parse collections, generate manifest lists
  - `worker.py`: Process single manifest (SLURM-compatible)
  - `output.py`: SHA1-based output paths, resume tracking

- `barnacle-config.example.yaml` - Configuration template
  - Storage paths (cache, output, models)
  - OCR settings (model, IIIF params)
  - SLURM resources (partition, CPUs, memory, time)
  - **NOTE**: Config file exists but NOT currently used by CLI/scripts

**Key design decision**: Per-manifest output files with SHA1 naming for parallel-safe processing

### Commit bc217a8: Add comprehensive test suite for IIIF and pipeline modules
**Date**: Jan 21, 2026

**Created test infrastructure:**
- `tests/fixtures/` - IIIF test data
  - `manifest_simple.json`: Valid 2-page manifest
  - `manifest_invalid.json`: Manifest missing image service
  - `collection_simple.json`: Collection with 2 manifests

- `tests/test_iiif_models.py` (15 tests)
  - Pydantic model parsing, methods (canvases(), image_url())

- `tests/test_iiif_validation.py` (10 tests)
  - Validation logic for manifests, collections, canvases

- `tests/test_iiif_traversal.py` (7 tests)
  - `iter_manifests()`, `is_collection()`, `is_manifest()`

- `tests/test_pipeline_output.py` (15 tests)
  - SHA1 path generation, page_key, resume tracking

**Result**: 47 tests, all passing

### Commit 2b1087c: Add Docker and SLURM deployment infrastructure
**Date**: Jan 22, 2026

**Containerization:**
- `Dockerfile` - Python 3.12-slim, PDM, libvips
  - Mount points: /models, /cache, /output
  - Entry point: `pdm run barnacle`

- `.dockerignore` - Optimized build context

**SLURM integration:**
- `scripts/prepare_collection.py`
  - Parses collection → manifest list (TSV)
  - Generates SHA1-based output paths

- `slurm/process_manifest.sh`
  - Job array worker script
  - Processes one manifest per array task
  - Singularity execution with bind mounts

- `slurm/run_collection.sh`
  - End-to-end workflow (prepare → submit → monitor)
  - Environment variable configuration

**Documentation:**
- `docs/docker.md` - Build, test, push workflow
- `docs/slurm.md` - HPC deployment, monitoring, troubleshooting

### Commit 0ebec1f: Refactor CLI to use new IIIF and pipeline modules
**Date**: Jan 22, 2026

**CLI modernization:**
- Removed 260 lines of duplicate code
- Now imports from `barnacle.iiif.v2` and `barnacle.pipeline`
- `ocr` command uses `process_manifest()` worker
- Same code path for local testing and cluster deployment

**Commands updated:**
- `validate`: Uses Pydantic models, added `--skip-manifests` flag
- `ocr`: Refactored to use pipeline worker, better progress reporting
- `sample-image-url`: Simplified with model methods

### Commit f86080c: Update README to reflect current production-ready status
**Date**: Jan 22, 2026

**README overhaul:**
- Status: "Early design" → "Production-ready MVP"
- Added Quick Start (installation, basic usage, HPC deployment)
- Architecture section with module breakdown
- Output format with JSONL schema example
- Documentation links (docker.md, slurm.md, deployment-plan.md)
- Development setup instructions
- Roadmap and acknowledgments

### Commits f059407 + d9a8da8: Add Kraken dependency and improve Docker docs
**Date**: Jan 24, 2026

**Dependency management:**
- Added `kraken>=5.2.0` to pyproject.toml (later updated to 6.0.3)
- Updated `requires-python` to `">=3.12,<3.13"` (Kraken constraint)
- Updated pdm.lock with Kraken 6.0.3 and ~80 dependencies

**Docker documentation:**
- Expanded DockerHub push instructions (step-by-step)
- Added prerequisites, verification, complete workflow
- Repository settings and tagging best practices
- Image size expectations (~2-3 GB)

**Docker testing results:**
- ✅ Build successful with Kraken 6.0.3
- ✅ OCR tested: 2 pages processed in 83 seconds
- ✅ Output validated: Proper JSONL format
- ✅ Volume mounts working (models, cache, output)

---

## Current Project State

### Architecture

```
Collection URL
    ↓
prepare_collection.py → manifests.txt (SHA1-based paths)
    ↓
SLURM Job Array (--array=1-N)
    ├─ Worker 1: process_manifest() → SHA1_1.jsonl
    ├─ Worker 2: process_manifest() → SHA1_2.jsonl
    └─ Worker N: process_manifest() → SHA1_N.jsonl
```

### Key Files

**Source Code:**
```
src/barnacle/
├── iiif/v2/
│   ├── __init__.py
│   ├── models.py           # Pydantic models
│   ├── loaders.py          # Load/parse IIIF JSON
│   ├── validation.py       # Validate for pipeline
│   └── traversal.py        # iter_manifests()
├── pipeline/
│   ├── __init__.py
│   ├── coordinator.py      # Collection → manifest list
│   ├── worker.py           # process_manifest()
│   └── output.py           # SHA1 paths, resume tracking
├── ocr.py                  # KrakenBackend
└── cli.py                  # Typer commands
```

**Tests:**
```
tests/
├── fixtures/
│   ├── manifest_simple.json
│   ├── manifest_invalid.json
│   └── collection_simple.json
├── test_iiif_models.py     (15 tests)
├── test_iiif_validation.py (10 tests)
├── test_iiif_traversal.py  (7 tests)
└── test_pipeline_output.py (15 tests)
```

**Deployment:**
```
Dockerfile                          # Container definition
.dockerignore                       # Build optimization
barnacle-config.example.yaml        # Config template (NOT USED YET)
scripts/prepare_collection.py      # Manifest list generator
slurm/process_manifest.sh           # Job array worker
slurm/run_collection.sh             # End-to-end orchestration
```

**Documentation:**
```
README.md                           # Project overview, quick start
docs/docker.md                      # Docker build, push, test
docs/slurm.md                       # HPC deployment guide
docs/deployment-plan.md             # Architecture design
docs/overview.md                    # Old MVP docs (consider archiving)
docs/roadmap.md                     # Old MVP docs (consider archiving)
docs/mvp/contracts.md               # Old MVP docs (consider archiving)
```

### Dependencies

**Python**: `>=3.12,<3.13` (Kraken constraint)

**Key packages:**
- `kraken==6.0.3` - OCR engine
- `pydantic>=2.8` - Type-safe models
- `httpx>=0.27` - HTTP client for IIIF
- `typer>=0.20.1` - CLI framework
- `rich>=13.7` - Terminal output
- `snakeviz>=2.2.2` - Profiling

**Dev dependencies:**
- `pytest>=8` - Testing
- `pytest-cov>=6` - Coverage
- `ruff>=0.6` - Linting/formatting

### Testing

**Run tests:**
```bash
pdm run pytest                # All tests
pdm run pytest -v             # Verbose
pdm run pytest --cov=barnacle # With coverage
```

**Current status**: 47 tests, all passing

### Docker

**Build:**
```bash
docker build -t barnacle:latest .
```

**Test locally:**
```bash
docker run --rm \
  -v $(pwd)/models:/models:ro \
  -v $(pwd)/docker_test/cache:/cache \
  -v $(pwd)/docker_test/output:/output \
  barnacle:latest ocr <MANIFEST_URL> \
    --model /models/McCATMuS_nfd_nofix_V1.mlmodel \
    --cache-dir /cache \
    --out /output/test.jsonl \
    --max-pages 2
```

**Status**: Built and tested successfully

### Just Recipes

**Still useful for local development:**
```bash
just test              # Run pytest
just lint              # Run ruff check
just format            # Run ruff format
just ocr-smoke         # Test OCR with 2 pages
just ocr-resume <URL>  # Resume-safe with SHA1 paths
just profile-ocr <URL> # Profile with cProfile
```

---

## TODO List

### Priority 1: Config File Integration

**Problem**: Config file exists (`barnacle-config.example.yaml`) but is NOT used by CLI or SLURM scripts. Everything uses command-line arguments.

**Tasks:**

1. **Create config loader module** (`src/barnacle/config.py`):
   ```python
   import yaml
   from pathlib import Path
   from typing import Optional, Dict, Any

   def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
       """Load configuration from YAML file.

       Search order:
       1. Explicit config_path parameter
       2. ./barnacle-config.yaml (current directory)
       3. ~/.barnacle/config.yaml (home directory)
       4. Return empty dict if none found
       """
       # Implementation here
   ```

2. **Update CLI** (`src/barnacle/cli.py`):
   - Add `--config PATH` option to commands
   - Load config at start, merge with CLI args
   - CLI args override config values
   - Use config defaults for: model, cache_dir, output paths, IIIF params

3. **Update pipeline worker** (`src/barnacle/pipeline/worker.py`):
   - Add optional `config: Dict[str, Any]` parameter
   - Use config for default values

4. **Update SLURM scripts**:
   - `slurm/process_manifest.sh`: Read config for default paths/resources
   - `slurm/run_collection.sh`: Source config, allow env vars to override

5. **Add dependency**:
   - Check if `pyyaml` is already in dependencies (it might be via Kraken)
   - If not: `pdm add pyyaml`

6. **Update documentation**:
   - README.md: Add config file usage to Quick Start
   - docs/docker.md: Show mounting config file
   - docs/slurm.md: Document config file usage

7. **Testing**:
   - Create `tests/test_config.py`
   - Test config loading, merging with CLI args
   - Test precedence: CLI > config > defaults

### Priority 2: DockerHub Deployment

**Ready to execute:**

```bash
# 1. Login
docker login

# 2. Tag (replace 'pulibrary' with actual username)
docker tag barnacle:latest pulibrary/barnacle:latest
docker tag barnacle:latest pulibrary/barnacle:v0.1.0

# 3. Push
docker push pulibrary/barnacle:latest
docker push pulibrary/barnacle:v0.1.0

# 4. Verify
docker pull pulibrary/barnacle:latest
```

**Reference**: `docs/docker.md` has complete instructions

### Priority 3: HPC Testing

**After DockerHub push:**

1. **Convert to Singularity** on Tufts HPC:
   ```bash
   singularity pull barnacle.sif docker://pulibrary/barnacle:latest
   ```

2. **Test single manifest**:
   ```bash
   singularity exec \
     --bind /project/barnacle/models:/models:ro \
     --bind /scratch/$USER/barnacle/cache:/cache \
     --bind /scratch/$USER/barnacle/runs:/output \
     barnacle.sif barnacle ocr <MANIFEST_URL> \
       --model /models/McCATMuS_nfd_nofix_V1.mlmodel \
       --cache-dir /cache \
       --out /output/test.jsonl \
       --max-pages 5
   ```

3. **Test SLURM job** with small collection (10-20 manifests):
   ```bash
   ./slurm/run_collection.sh <COLLECTION_URL> test_batch
   ```

4. **Monitor** and verify outputs

5. **Production run** with full Lapidus collection

### Priority 4: Documentation Cleanup (Optional)

**Old MVP docs to archive or remove:**
- `docs/overview.md` (outdated)
- `docs/roadmap.md` (outdated)
- `docs/mvp/contracts.md` (outdated)

**Consider:**
- Move to `docs/archive/` or delete
- All current info is in README.md and deployment guides

### Future Enhancements (Backlog)

- **GitHub Actions**: Automate Docker build/push on release tags
- **IIIF Presentation 3.0**: Add support for newer IIIF version
- **Web Annotations**: Output format for attaching OCR to IIIF
- **Additional OCR engines**: Tesseract support
- **Post-processing**: Text normalization, dehyphenation, ligature expansion
- **Quality metrics**: Confidence scores, ground truth validation
- **API server**: RESTful API for on-demand OCR
- **Kubernetes**: Cloud deployment alternative to SLURM

---

## Important Context

### Design Decisions Made

1. **Per-manifest output files** (not collection-level)
   - Enables parallel processing without file contention
   - SHA1 naming from manifest URL for determinism
   - Resume-safe at page level via `page_key`

2. **SLURM job arrays** (not Kanban/bucket model)
   - User asked about Grin Siphon's Kanban approach
   - Decided SLURM is simpler for single-stage pipeline
   - HPC-native solution, no custom orchestration needed

3. **Python 3.12 only** (not 3.13)
   - Kraken 6.0.3 requires `<3.13`
   - Had to update `requires-python` constraint

4. **Modular architecture**
   - IIIF models, pipeline, OCR as separate modules
   - CLI is thin wrapper over pipeline modules
   - Same code for local testing and HPC deployment

### User Preferences

- **Tufts HPC cluster**: Uses SLURM, builds Docker → DockerHub → Singularity
- **Lapidus collection**: Initial target for production processing
- **McCATMuS model**: Historical print OCR model (via Zenodo DOI)
- **justfile**: User likes it, keep it for development workflows

### Files NOT Committed (Intentional)

- `docker_test/` - Local testing directory
- `docs/dev-bookmark.md` - Personal notes
- `manifests_smoke.txt` - Test manifest URLs
- `.barnacle-cache/` - Local image cache
- `out.jsonl`, `profile.prof` - Temporary outputs

---

## Quick Commands (Resume Work)

```bash
# Navigate to project
cd /Users/wulfmanc/repos/gh/pulibrary/barnacle

# Check status
git status
git log --oneline -5

# Verify environment
pdm --version          # Should be 2.26.x
pdm list | grep kraken # Should show 6.0.3
just test              # Should pass all 47 tests

# Check Docker
docker images | grep barnacle  # Should show barnacle:latest

# Start config integration (Priority 1)
# 1. Create src/barnacle/config.py
# 2. Update CLI to load config
# 3. Test with pytest
```

---

## Session Timeline

- **Previous sessions**: MVP development, Collection handling fix
- **Jan 21, 2026**: Created IIIF models, pipeline modules, tests
- **Jan 22, 2026**: Added Docker/SLURM infrastructure, refactored CLI, updated README
- **Jan 24, 2026**: Added Kraken dependency, tested Docker, improved docs
- **Current**: Ready for config integration, DockerHub push, HPC testing

---

## Contact Points

**Key stakeholders:**
- Tufts HPC cluster managers (for deployment)
- Kraken developers (for OCR engine support)
- IIIF community (for standards compliance)
- McCATMuS project (for historical print models)

**Resources:**
- IIIF Presentation 2.1: https://iiif.io/api/presentation/2.1/
- Kraken docs: https://kraken.re/
- Tufts HPC docs: https://tuftsrt.github.io/Container_Training.github.io/
- McCATMuS model: DOI 10.5281/zenodo.14585602

---

## Notes for Next Session

1. **Config integration is highest priority** - It was created but never wired up
2. **DockerHub push is ready** - Just need to execute the commands
3. **All tests pass** - Code is in good shape
4. **Documentation is comprehensive** - docker.md and slurm.md have all the details
5. **Consider archiving old MVP docs** - overview.md, roadmap.md are outdated

**The system is production-ready. Main gap is config file integration for easier CLI usage.**
