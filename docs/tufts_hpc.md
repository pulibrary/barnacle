# Tufts HPC Cluster Guide

This guide covers deploying and running Barnacle on the Tufts HPC cluster using the `container-mod` module system.

## Prerequisites

- Access to Tufts HPC cluster
- Barnacle Docker image available on DockerHub (`cwulfman01/barnacle`)
- Access to the research storage allocation at `/cluster/tufts/lapidusocr/`

## Storage Layout

> **Note:** `/scratch` is not reliably available on the Tufts cluster. Use the research storage allocation instead.

```
/cluster/tufts/lapidusocr/
├── shared/
│   └── ocr/                   # Output JSONL files (shared across team)
└── cwulfm01/
    ├── cache/                  # Image cache (per-user, transient)
    └── logs/                   # SLURM job logs (per-user)
```

Create these directories once:

```bash
mkdir -p /cluster/tufts/lapidusocr/shared/ocr
mkdir -p /cluster/tufts/lapidusocr/cwulfm01/cache
mkdir -p /cluster/tufts/lapidusocr/cwulfm01/logs
```

## Quick Start

```bash
# Load barnacle module
module load use.own
module load barnacle/latest

# Submit a job array (one task per manifest)
N=$(wc -l < ~/barnacle/data/manifests/tranche-01.txt)
sbatch --array=1-${N}%50 \
  --output=/cluster/tufts/lapidusocr/cwulfm01/logs/barnacle-%A_%a.out \
  --error=/cluster/tufts/lapidusocr/cwulfm01/logs/barnacle-%A_%a.err \
  --mail-user=cwulfm01@tufts.edu \
  --export=ALL,MANIFEST_LIST=$HOME/barnacle/data/manifests/tranche-01.txt,OUTPUT_DIR=/cluster/tufts/lapidusocr/shared/ocr,MODEL=$HOME/barnacle/models/catmus-print-fondue-large.mlmodel,CACHE_BASE=/cluster/tufts/lapidusocr/cwulfm01/cache \
  slurm/process_manifest_module.sh
```

> **Important:** The `--export` value must have no spaces between comma-separated entries or SLURM will misparse it.

## Installation Methods

The Tufts HPC cluster provides two methods for running containerized applications:

1. **container-mod** (Recommended) - Integrates containers into the module system
2. **Direct Singularity** - Manual container management

### Using container-mod (Recommended)

The [container-mod](https://rtguides.it.tufts.edu/bio/tutorials/container-mod.html) tool on Tufts HPC simplifies containerized application deployment by automating image retrieval and module file generation. This is the recommended approach for most users.

#### Step 1: Load container-mod

```bash
module load container-mod
```

#### Step 2: Create the barnacle module

Use the `pipe` subcommand with the `-p` (personal) flag to pull the image, generate a module file, and create executable wrappers:

```bash
container-mod pipe -p docker://cwulfman01/barnacle:latest
```

This will:
- Pull the Docker image and convert it to Singularity format
- Generate a module file in your `$HOME/privatemodules` directory
- Create wrapper scripts for the barnacle executable

#### Step 3: Load and use barnacle

```bash
# Enable your personal modules
module load use.own

# Load barnacle
module load barnacle/latest

# Verify installation
barnacle --help
```

#### Step 4: Run OCR

Once the module is loaded, you can use barnacle directly.

**Batch processing (recommended):**

```bash
# Create a file with manifest URLs (one per line)
cat > manifests.txt << EOF
https://figgy.princeton.edu/concern/scanned_resources/abc123/manifest
https://figgy.princeton.edu/concern/scanned_resources/def456/manifest
EOF

# Process all manifests (uses default model, auto-resumes)
barnacle run manifests.txt /scratch/$USER/barnacle/output --max-pages 5
```

The `run` command creates SHA1-named output files for each manifest and automatically skips already-processed manifests on restart.

**Using sbatch (job array):**

See the Quick Start section above. Use `slurm/process_manifest_module.sh` for module-based submission.

**Single manifest (testing only):**

```bash
barnacle ocr \
  https://figgy.princeton.edu/concern/scanned_resources/<ID>/manifest \
  --model ~/barnacle/models/catmus-print-fondue-large.mlmodel \
  --cache-dir /cluster/tufts/lapidusocr/cwulfm01/cache \
  --out /cluster/tufts/lapidusocr/shared/ocr/test.jsonl \
  --max-pages 5
```

> **Note:** `barnacle ocr` requires `--model` explicitly. Unlike `barnacle run`, it has no default.

#### Updating to a new version

When a new version is released, update your module:

```bash
module load container-mod

# Pull and install a specific version
container-mod pipe -p docker://cwulfman01/barnacle:v0.2.0

# Or force update to latest
container-mod pipe -p -f docker://cwulfman01/barnacle:latest
```

#### Group/Lab shared installation

For shared installations across a research group, group managers can use profiles:

```bash
# Create a profile for your group (one-time setup by group manager)
container-mod pipe --profile mygroup docker://cwulfman01/barnacle:latest

# Group members can then load the shared module
module load barnacle/latest
```

See the [Tufts container-mod documentation](https://rtguides.it.tufts.edu/bio/tutorials/container-mod.html) for details on setting up group profiles.

### Using Singularity Directly

For users who prefer manual container management or need more control over bind mounts.

#### Pull and Convert to Singularity

On the HPC login node:

```bash
# Pull from DockerHub and convert to Singularity
singularity pull barnacle.sif docker://cwulfman01/barnacle:latest
```

#### Test with Singularity

```bash
# Test help
singularity exec barnacle.sif barnacle --help

# Test OCR with bind mounts
singularity exec \
  --bind /path/to/models:/models:ro \
  --bind /path/to/cache:/cache \
  --bind /path/to/output:/output \
  barnacle.sif barnacle ocr \
    https://figgy.princeton.edu/concern/scanned_resources/<ID>/manifest \
    --model /models/catmus-print-fondue-large.mlmodel \
    --cache-dir /cache \
    --out /output/test.jsonl \
    --max-pages 5
```

## Volume Mounts (Singularity only)

If using Singularity directly rather than `container-mod`, the container expects three volumes to be mounted:

| Mount Point | Purpose | Tufts HPC Path |
|------------|---------|------------------|
| `/models` | Kraken model files (read-only) | `~/barnacle/models` |
| `/cache` | Downloaded images (read-write) | `/cluster/tufts/lapidusocr/$USER/cache` |
| `/output` | OCR output JSONL files (read-write) | `/cluster/tufts/lapidusocr/shared/ocr` |

## Administrator Configuration

HPC administrators can create a custom modulefile that uses container-mod to expose barnacle with specific bind mounts:

```tcl
#%Module1.0
module-whatis "Barnacle OCR pipeline for IIIF manifests"

# Container image location
set container_image /cluster/software/containers/barnacle.sif

# Use container-mod to expose the barnacle command
container-mod load $container_image
container-mod exec barnacle /usr/local/bin/barnacle
```

### Bind Mounts for container-mod

When configuring container-mod, ensure the following paths are bind-mounted:

| Container Path | Purpose | Suggested Host Path |
|----------------|---------|---------------------|
| `/models` | Kraken model files (read-only) | `/cluster/shared/barnacle/models` |
| `/cache` | Downloaded images (read-write) | User scratch or temp directory |
| `/output` | OCR output files (read-write) | User scratch directory |

## Time Limits and Recovery

### Default time limit

`slurm/process_manifest_module.sh` requests `#SBATCH --time=12:00:00` by default.
Large manifests or slow IIIF servers (e.g. rate-limited figgy.princeton.edu) can take
several hours per task. You can override the default on the command line:

```bash
sbatch --array=... --time=16:00:00 ... slurm/process_manifest_module.sh
```

A `--time` flag on the `sbatch` command line **overrides** the `#SBATCH` directive
inside the script, so no script edits are needed.

### Recovering from timed-out tasks

If tasks exceed the time limit, barnacle's resume mechanism means no work is lost —
resubmitting a task will skip pages that are already written. Use
`scripts/find_incomplete.py` to identify which manifests need resubmission:

```bash
# Full check: missing/empty files AND timed-out jobs detected from logs
python3 scripts/find_incomplete.py \
    ~/barnacle/data/manifests/tranche-01.txt \
    /cluster/tufts/lapidusocr/shared/ocr \
    --logs-dir /cluster/tufts/lapidusocr/cwulfm01/logs \
    > ~/barnacle/data/manifests/tranche-01-recovery.txt

wc -l ~/barnacle/data/manifests/tranche-01-recovery.txt  # how many to resubmit
```

> **Note:** Do not use `.err` files to detect failures — barnacle's Python logging
> (INFO level) writes to stderr, so every job (including successful ones) produces a
> non-empty `.err` file. The `--logs-dir` check instead looks at `.out` files for the
> word `SUCCESS`, which is only printed on clean exit. Jobs killed by SLURM's time
> limit never reach that line.

Then resubmit with a longer time limit:

```bash
N=$(wc -l < ~/barnacle/data/manifests/tranche-01-recovery.txt)
sbatch --array=1-${N}%50 \
  --time=12:00:00 \
  --output=/cluster/tufts/lapidusocr/cwulfm01/logs/barnacle-%A_%a.out \
  --error=/cluster/tufts/lapidusocr/cwulfm01/logs/barnacle-%A_%a.err \
  --mail-user=cwulfm01@tufts.edu \
  --export=ALL,MANIFEST_LIST=$HOME/barnacle/data/manifests/tranche-01-recovery.txt,OUTPUT_DIR=/cluster/tufts/lapidusocr/shared/ocr,MODEL=$HOME/barnacle/models/catmus-print-fondue-large.mlmodel,CACHE_BASE=/cluster/tufts/lapidusocr/cwulfm01/cache \
  slurm/process_manifest_module.sh
```

`scripts/run_stats.py` can track overall progress across the original tranche
while the recovery job runs.

## Troubleshooting

### Architecture Mismatch Errors

If you see errors like `exec format error` or the container fails to start, the image was likely built for the wrong architecture:

```bash
# The image should be built for linux/amd64
# If you're building locally on Apple Silicon, use:
docker build --platform linux/amd64 -t barnacle:latest .
```

See [docker.md](docker.md) for build instructions.

### Permission Errors

If you encounter permission errors with Singularity bind mounts:

```bash
# Run with your user ID explicitly
singularity exec --bind /path/to/data:/data \
  --home /tmp \
  barnacle.sif barnacle ...
```

### libvips Errors

If Kraken fails with image processing errors:

```bash
# Ensure libvips is installed in container (should be in Dockerfile)
singularity exec barnacle.sif dpkg -l | grep libvips
```

### Model Not Found

If Kraken can't find the model:

```bash
# Verify bind mount and model path
ls -l /path/to/models/
singularity exec --bind /path/to/models:/models barnacle.sif ls -l /models/
```

## Troubleshooting

### `/scratch` not available

Tufts `/scratch` has known availability issues. Use `/cluster/tufts/lapidusocr/$USER/cache` instead, as shown in the Quick Start above.

### `--model` is required

`barnacle ocr` requires `--model` explicitly — it has no built-in default. Always pass a filesystem path or DOI. The `process_manifest_module.sh` script accepts a `MODEL` environment variable (defaults to the CATMuS Print Fondue Large DOI).

### Spaces in `--export` cause parse errors

SLURM's `--export` option must not contain spaces between entries:
```bash
# Wrong (spaces after commas)
--export=ALL,MANIFEST_LIST=foo.txt, MODEL=/path/to/model

# Correct
--export=ALL,MANIFEST_LIST=foo.txt,MODEL=/path/to/model
```

## Next Steps

Once running, proceed to:

1. Monitor with `squeue -u $USER` and `sacct`
2. Check output counts: `ls /cluster/tufts/lapidusocr/shared/ocr/*.jsonl | wc -l`
3. Resubmit any failed tasks by array task ID

See `docs/slurm.md` for full SLURM integration details.
