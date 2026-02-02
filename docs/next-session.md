# Next Session Reminders

## Session Summary (2026-01-24)

Completed production-ready MVP with HPC deployment infrastructure:
- ✅ IIIF v2 models and pipeline modules
- ✅ Comprehensive test suite (47 tests passing)
- ✅ Docker container tested and working
- ✅ SLURM job array scripts
- ✅ CLI refactored to use new modules
- ✅ Kraken 6.0.3 added as dependency
- ✅ Documentation updated (README, docker.md, slurm.md)

**Status**: Production-ready, 6 commits created

## Pending Tasks

### 1. Integrate Config File Support

**Current State:**
- Config file exists: `barnacle-config.example.yaml` (created in commit 10b4d27)
- Contains settings for storage paths, OCR, SLURM, container
- Currently **NOT** used by CLI or SLURM scripts
- Everything uses command-line arguments instead

**What to Do:**
Add config file loading to CLI and pipeline modules:

```python
# Add to barnacle/config.py (new module)
import yaml
from pathlib import Path
from typing import Optional

def load_config(config_path: Optional[Path] = None) -> dict:
    """Load configuration from YAML file."""
    if config_path is None:
        # Check default locations
        candidates = [
            Path("barnacle-config.yaml"),
            Path.home() / ".barnacle" / "config.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = candidate
                break

    if config_path and config_path.exists():
        with config_path.open() as f:
            return yaml.safe_load(f)
    return {}
```

**Integration Points:**
1. **CLI** (`src/barnacle/cli.py`):
   - Add `--config` option to commands
   - Load config file, merge with CLI args (CLI args override config)
   - Use config defaults for paths, model, IIIF params

2. **Pipeline worker** (`src/barnacle/pipeline/worker.py`):
   - Accept config dict parameter
   - Use config for defaults

3. **SLURM scripts** (`slurm/process_manifest.sh`, `slurm/run_collection.sh`):
   - Read config for default paths and resources
   - Allow environment variables to override

**Files to Update:**
- Create `src/barnacle/config.py`
- Update `src/barnacle/cli.py` (add --config option, load config)
- Update `src/barnacle/pipeline/worker.py` (accept config parameter)
- Update `slurm/process_manifest.sh` (source config if available)
- Update `pyproject.toml` (add `pyyaml` dependency if needed)
- Update docs to document config file usage

### 2. Deploy to DockerHub

**Ready to push:**
```bash
docker login
docker tag barnacle:latest cwulfman01/barnacle:latest
docker tag barnacle:latest cwulfman01/barnacle:v0.1.0
docker push cwulfman01/barnacle:latest
docker push cwulfman01/barnacle:v0.1.0
```

Instructions in `docs/docker.md`

### 3. HPC Testing Plan

Once Docker image is on DockerHub:

1. **Convert to Singularity** on Tufts HPC:
   ```bash
   singularity pull barnacle.sif docker://cwulfman01/barnacle:latest
   ```

2. **Test single manifest**:
   ```bash
   singularity exec --bind /models:/models:ro \
     --bind /cache:/cache --bind /output:/output \
     barnacle.sif barnacle ocr <MANIFEST_URL> \
       --model /models/model.mlmodel --out /output/test.jsonl
   ```

3. **Test SLURM job** with small collection (10-20 manifests)

4. **Production run** with full Lapidus collection

## Files Reference

**Config File:**
- `barnacle-config.example.yaml` - Example configuration (committed)
- Users copy to `barnacle-config.yaml` (gitignored)

**Key Modules:**
- `src/barnacle/iiif/v2/` - IIIF models, loaders, validation
- `src/barnacle/pipeline/` - coordinator, worker, output
- `src/barnacle/cli.py` - Command-line interface

**Deployment:**
- `Dockerfile` - Container definition
- `slurm/process_manifest.sh` - Job array worker
- `slurm/run_collection.sh` - End-to-end orchestration
- `scripts/prepare_collection.py` - Manifest list generation

**Documentation:**
- `README.md` - Project overview, quick start
- `docs/docker.md` - Docker build, push, test
- `docs/slurm.md` - HPC deployment guide
- `docs/deployment-plan.md` - Architecture design

## Recent Commits (main branch)

```
d9a8da8 Updates kraken dependency from 5.2.0 to 6.0.3
f059407 Add Kraken as explicit dependency and improve Docker docs
f86080c Update README to reflect current production-ready status
0ebec1f Refactor CLI to use new IIIF and pipeline modules
2b1087c Add Docker and SLURM deployment infrastructure
bc217a8 Add comprehensive test suite for IIIF and pipeline modules
10b4d27 Add IIIF models and pipeline modules for HPC deployment
```

## Quick Start (Next Session)

```bash
# Resume work
cd /Users/wulfmanc/repos/gh/pulibrary/barnacle
git status

# Check current state
just test                    # Run tests (should pass)
docker images | grep barnacle  # Check Docker image exists
pdm list | grep kraken        # Verify Kraken installed

# Start with config integration
# 1. Create src/barnacle/config.py
# 2. Add pyyaml to dependencies if needed
# 3. Update CLI to load config
```

## Notes

- **Python version**: `>=3.12,<3.13` (Kraken constraint)
- **Kraken version**: 6.0.3
- **Test suite**: 47 tests, all passing
- **justfile**: Still relevant and useful for local testing
- **docker_test/**: Local test directory (not committed)
