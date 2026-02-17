# Session Context: Barnacle (2026-02-17)

## Executive Summary

Switched to new Kraken OCR model, fixed batch processing bugs, and began processing tranche-01 on the Kraken VM. Awaiting meeting with Tufts HPC team before further action.

**Current Status:** Batch processing running on VM with 12 parallel jobs

---

## What Was Accomplished This Session

### 1. Model Update
- **Old model:** McCATMuS_nfd_nofix_V1 (DOI: 10.5281/zenodo.14585602)
- **New model:** catmus-print-fondue-large (DOI: 10.5281/zenodo.10592716)
- Updated all references in code, scripts, and documentation
- Model file added to repository: `models/catmus-print-fondue-large.mlmodel`

### 2. Bug Fixes
- **batch_process.sh SHA1 bug:** Command substitution was inside single quotes, causing literal `$(echo...` filenames instead of SHA1 hashes
- **Fix:** Replaced inline command with exported `process_manifest()` function
- **macOS compatibility:** Changed `sha1sum` to `shasum -a 1`

### 3. New Features
- Added `--log-level` option to `batch_process.sh`

### 4. Releases
- Tagged and pushed `v0.3.0`
- Docker build completed successfully on GitHub Actions
- Images available: `cwulfman01/barnacle:0.3.0` and `cwulfman01/barnacle:latest`

---

## Current Batch Processing Status

### VM: kraken (pulsys@kraken)

**Specs:**
- 16 CPUs (Intel Xeon Gold 6126 @ 2.60GHz)
- 62GB RAM (mostly unused)
- Spinning disks (HDD) + ZFS tank at /barnacle
- No GPU

**Currently Running:**
```bash
./scripts/batch_process.sh \
    --manifest-list data/manifests/tranche-01.txt \
    --output-dir ./output \
    --model 10.5281/zenodo.10592716 \
    --jobs 12 \
    --log-level INFO
```

**Performance Benchmarks:**
| Image Size | Time per Page |
|------------|---------------|
| `!3000,3000` (default) | ~4.5 min |
| `!2000,2000` | ~4.0 min |

**Estimated Time for tranche-01:**
- 500 manifests × ~50 pages × 4 min = ~1,667 CPU-hours
- With 12 parallel jobs: ~139 hours (~6 days)

### Processing Architecture
```
data/manifests/
├── all.txt           # Complete list (2,853 URLs)
├── tranche-01.txt    # URLs 1-500 (current - VM)
├── tranche-02.txt    # URLs 501-1000 (HPC)
├── tranche-03.txt    # URLs 1001-1500 (HPC)
├── tranche-04.txt    # URLs 1501-2000 (HPC)
├── tranche-05.txt    # URLs 2001-2500 (HPC)
└── tranche-06.txt    # URLs 2501-2853 (VM)
```

---

## Key Files Modified This Session

| File | Changes |
|------|---------|
| `src/barnacle/ocr.py` | Updated DEFAULT_MODEL DOI |
| `scripts/batch_process.sh` | Fixed SHA1 bug, added --log-level option |
| `justfile` | Updated model path |
| `slurm/run_collection.sh` | Updated model path |
| `README.md` | Updated model DOI references |
| `docs/batch-processing.md` | Updated model DOI (14 references) |
| `docs/docker.md` | Updated model references |
| `docs/slurm.md` | Updated model references |
| `docs/tufts_hpc.md` | Updated model references |
| `docs/deployment-plan.md` | Updated model references |

---

## Commits This Session

```
decf9c1 Update remaining model DOI references to catmus-print-fondue-large
10dde62 Add --log-level option to batch_process.sh
638d2fc Fix batch_process.sh command substitution and macOS compatibility
886d8c8 Update default Kraken model to catmus-print-fondue-large
```

All pushed to origin/main. Tag v0.3.0 pushed.

---

## Pending / Next Steps

### Immediate
1. **Monitor tranche-01 processing** on VM
   - Check progress: `ls ./output/*.jsonl | wc -l`
   - Check joblog: `cat batch_*.log | tail`

2. **Meet with Tufts HPC team** to discuss:
   - Running tranches 02-05 on HPC
   - SLURM job array configuration
   - Resource allocation (CPUs, memory, time limits)

### Future Enhancements
1. **Add `--size` option to batch_process.sh** - Allow configuring IIIF image size
2. **Add `--cache-dir` option to batch_process.sh** - Allow specifying cache location
3. **Config file integration** - Wire up `barnacle-config.yaml` for defaults

---

## Quick Resume Commands

```bash
# SSH to VM
ssh pulsys@kraken

# Check batch progress
cd ~/barnacle
ls ./output/*.jsonl | wc -l
tail -f batch_*.log

# If interrupted, resume with:
./scripts/batch_process.sh \
    --manifest-list data/manifests/tranche-01.txt \
    --output-dir ./output \
    --model 10.5281/zenodo.10592716 \
    --jobs 12 \
    --resume \
    --joblog batch_XXXXXXXX_XXXXXX.log \
    --log-level INFO
```

---

## Reference

**Repositories:**
- GitHub: https://github.com/pulibrary/barnacle
- DockerHub: https://hub.docker.com/r/cwulfman01/barnacle

**Model:**
- catmus-print-fondue-large
- DOI: 10.5281/zenodo.10592716
- Local path: `models/catmus-print-fondue-large.mlmodel`

**Documentation:**
- [Batch Processing Guide](batch-processing.md)
- [Docker Guide](docker.md)
- [SLURM Guide](slurm.md)
- [Tufts HPC Guide](tufts_hpc.md)
