# Tufts HPC Cluster Guide

This guide covers deploying and running Barnacle on the Tufts HPC cluster using Singularity containers.

## Prerequisites

- Access to Tufts HPC cluster
- Barnacle Docker image available on DockerHub (`cwulfman01/barnacle`)

## Quick Start

```bash
# Load container-mod
module load container-mod

# Install barnacle as a personal module
container-mod pipe -p docker://cwulfman01/barnacle:latest

# Load the module
module load use.own
module load barnacle/latest

# Run OCR on multiple manifests (batch mode)
barnacle run manifests.txt /scratch/$USER/barnacle/output

# Or run OCR on a single manifest
barnacle ocr https://example.com/manifest \
  --model /path/to/model.mlmodel \
  --out /scratch/$USER/output.jsonl
```

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

**Single manifest:**

```bash
barnacle ocr \
  https://figgy.princeton.edu/concern/scanned_resources/<ID>/manifest \
  --model /path/to/models/catmus-print-fondue-large.mlmodel \
  --cache-dir /scratch/$USER/barnacle/cache \
  --out /scratch/$USER/barnacle/output/results.jsonl \
  --max-pages 5
```

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

## Volume Mounts

The container expects three volumes to be mounted:

| Mount Point | Purpose | Example HPC Path |
|------------|---------|------------------|
| `/models` | Kraken model files (read-only) | `/project/barnacle/models` |
| `/cache` | Downloaded images (read-write) | `/scratch/$USER/barnacle/cache` |
| `/output` | OCR output JSONL files (read-write) | `/scratch/$USER/barnacle/runs` |

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

## Next Steps

Once the Singularity container is working on the HPC cluster, proceed to:

1. Set up SLURM job array scripts (`slurm/process_manifest.sh`)
2. Test parallel processing with a small collection
3. Scale up to full production workloads

See `docs/slurm.md` for SLURM integration details.
