# Docker Deployment Guide

This guide covers building, testing, and deploying the Barnacle container for the Tufts HPC cluster.

## Workflow Overview

The Tufts HPC deployment follows this pattern:

1. **Build** Docker image locally or in CI
2. **Push** to DockerHub
3. **Pull** and convert to Singularity on HPC cluster
4. **Run** via Singularity with SLURM

## Prerequisites

- Docker installed locally
- DockerHub account (for pushing images)
- Access to Tufts HPC cluster with Singularity

## Architecture Notes

The HPC cluster runs on Intel/AMD processors (linux/amd64). If building on Apple Silicon (M1/M2/M3), you must specify the target platform to ensure compatibility:

```bash
docker build --platform linux/amd64 -t barnacle:latest .
```

All build commands in this guide include the `--platform linux/amd64` flag. This ensures the image will run correctly on the HPC cluster regardless of your local machine's architecture.

> **Note:** Building for a different architecture uses emulation and will be slower than native builds. This is expected behavior.

## Building the Docker Image

### Basic Build

```bash
# From project root
docker build --platform linux/amd64 -t barnacle:latest .
```

### Tagged Build

```bash
# Tag with version
docker build --platform linux/amd64 -t barnacle:v0.1.0 .

# Tag for DockerHub (replace 'yourusername')
docker build --platform linux/amd64 -t yourusername/barnacle:latest .
docker build --platform linux/amd64 -t yourusername/barnacle:v0.1.0 .
```

### Build with Model Pre-installed (Optional)

If you want to bake the Kraken model into the image:

```bash
# Build with custom Dockerfile that includes model download
docker build --platform linux/amd64 -t barnacle:latest \
  --build-arg MODEL_DOI=10.5281/zenodo.14585602 \
  .
```

## Testing Locally with Docker

### Test Help Command

```bash
docker run --rm barnacle:latest --help
```

### Test with Sample Manifest

```bash
# Create local directories for volumes
mkdir -p models cache output

# Download Kraken model (if not baked into image)
# Place model file in ./models/

# Run OCR on small manifest
docker run --rm \
  -v $(pwd)/models:/models:ro \
  -v $(pwd)/cache:/cache \
  -v $(pwd)/output:/output \
  barnacle:latest ocr \
    https://figgy.princeton.edu/concern/scanned_resources/22a5dd98-7a15-4ed9-bdbc-16bb4ae785b6/manifest \
    --model /models/McCATMuS_nfd_nofix_V1.mlmodel \
    --cache-dir /cache \
    --out /output/test.jsonl \
    --max-pages 5
```

### Interactive Shell (for debugging)

```bash
docker run --rm -it \
  -v $(pwd)/models:/models:ro \
  -v $(pwd)/cache:/cache \
  -v $(pwd)/output:/output \
  --entrypoint /bin/bash \
  barnacle:latest
```

## Pushing to DockerHub

### Prerequisites

- DockerHub account (sign up at https://hub.docker.com)
- Docker image built locally (`barnacle:latest`)

### Step 1: Login

```bash
docker login
# Enter your DockerHub username and password (or access token)
```

### Step 2: Tag the Image

Tag your local image with your DockerHub username:

```bash
# Format: docker tag <local-image> <dockerhub-username>/<repository-name>:<tag>
docker tag barnacle:latest yourusername/barnacle:latest

# Also tag with version number for releases
docker tag barnacle:latest yourusername/barnacle:v0.1.0
```

**Example** (if your username is `pulibrary`):
```bash
docker tag barnacle:latest pulibrary/barnacle:latest
docker tag barnacle:latest pulibrary/barnacle:v0.1.0
```

### Step 3: Push to DockerHub

```bash
docker push yourusername/barnacle:latest
docker push yourusername/barnacle:v0.1.0
```

The push will take several minutes depending on your upload speed (image is ~2-3 GB with dependencies).

### Step 4: Verify the Upload

Check that the image is available:

```bash
# Visit in browser
https://hub.docker.com/r/yourusername/barnacle

# Or test pulling
docker pull yourusername/barnacle:latest
```

### Complete Example Workflow

```bash
# 1. Build the image
docker build --platform linux/amd64 -t barnacle:latest .

# 2. Login to DockerHub
docker login

# 3. Tag with your username (replace 'pulibrary')
docker tag barnacle:latest pulibrary/barnacle:latest
docker tag barnacle:latest pulibrary/barnacle:v0.1.0

# 4. Push both tags
docker push pulibrary/barnacle:latest
docker push pulibrary/barnacle:v0.1.0

# 5. Verify
docker pull pulibrary/barnacle:latest
```

### Repository Settings

- **Privacy**: Repository will be public by default (can be changed in DockerHub settings)
- **Auto-creation**: Repository will be created automatically on first push
- **Tags**: Using both `latest` and version tags (e.g., `v0.1.0`) is recommended for tracking releases

### Tagging Best Practices

- `latest`: Always points to the most recent stable build
- `v0.1.0`, `v0.2.0`, etc.: Specific version releases
- `dev`: Development/unstable builds (optional)
- Git commit SHA: For exact reproducibility (optional)

## Using on Tufts HPC Cluster

### Pull and Convert to Singularity

On the HPC login node:

```bash
# Pull from DockerHub and convert to Singularity
singularity pull barnacle.sif docker://yourusername/barnacle:latest

# Or build from Docker daemon (if Docker image is available locally)
docker save yourusername/barnacle:latest | singularity build barnacle.sif docker-archive:/dev/stdin
```

### Test with Singularity

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
    --model /models/McCATMuS_nfd_nofix_V1.mlmodel \
    --cache-dir /cache \
    --out /output/test.jsonl \
    --max-pages 5
```

## container-mod Integration

[container-mod](https://github.com/cea-hpc/modules-container) is a CEA extension for Environment Modules that allows containerized applications to be used as regular module commands on HPC clusters. The barnacle container is designed to work with container-mod.

### How It Works

The barnacle executable is installed directly at `/usr/local/bin/barnacle`, making it callable without going through an entrypoint wrapper. This allows container-mod to expose `barnacle` as a native command to users who load the module.

### Verifying Direct Execution

To confirm the container supports direct execution (required for container-mod):

```bash
# Build the image
docker build --platform linux/amd64 -t barnacle:test .

# Verify barnacle is in PATH
docker run --rm barnacle:test which barnacle
# Should show: /usr/local/bin/barnacle

# Test calling barnacle directly (bypassing entrypoint)
docker run --rm --entrypoint "" barnacle:test barnacle --help
```

### Example container-mod Configuration

HPC administrators can create a modulefile that uses container-mod to expose barnacle. Here's an example configuration:

```tcl
#%Module1.0
module-whatis "Barnacle OCR pipeline for IIIF manifests"

# Container image location
set container_image /cluster/software/containers/barnacle.sif

# Use container-mod to expose the barnacle command
container-mod load $container_image
container-mod exec barnacle /usr/local/bin/barnacle
```

With this configuration, users can simply run:

```bash
module load barnacle
barnacle ocr https://example.com/manifest --model /models/model.mlmodel
```

### Bind Mounts for container-mod

When configuring container-mod, ensure the following paths are bind-mounted:

| Container Path | Purpose | Suggested Host Path |
|----------------|---------|---------------------|
| `/models` | Kraken model files (read-only) | `/cluster/shared/barnacle/models` |
| `/cache` | Downloaded images (read-write) | User scratch or temp directory |
| `/output` | OCR output files (read-write) | User scratch directory |

## Volume Mounts

The container expects three volumes to be mounted:

| Mount Point | Purpose | Example HPC Path |
|------------|---------|------------------|
| `/models` | Kraken model files (read-only) | `/project/barnacle/models` |
| `/cache` | Downloaded images (read-write) | `/scratch/$USER/barnacle/cache` |
| `/output` | OCR output JSONL files (read-write) | `/scratch/$USER/barnacle/runs` |

## Troubleshooting

### Architecture Mismatch Errors

If you see errors like `exec format error` or the container fails to start on the HPC cluster, the image was likely built for the wrong architecture:

```bash
# Check the image architecture
docker inspect barnacle:latest | grep Architecture
# Should show: "Architecture": "amd64"

# If it shows "arm64", rebuild with the platform flag
docker build --platform linux/amd64 -t barnacle:latest .
```

This commonly happens when building on Apple Silicon Macs without specifying `--platform linux/amd64`.

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

## CI/CD Integration (Optional)

To automate Docker builds and pushes with GitHub Actions, see `.github/workflows/docker-build.yml` (if configured).

## Next Steps

Once the Singularity container is working on the HPC cluster, proceed to:

1. Set up SLURM job array scripts (`slurm/process_manifest.sh`)
2. Test parallel processing with a small collection
3. Scale up to full production workloads

See `docs/slurm.md` for SLURM integration details.
