# Docker Build and Push Guide

This guide covers building, testing, and pushing the Barnacle Docker image to DockerHub.

## Prerequisites

- Docker installed locally
- DockerHub account (for pushing images)

## Quick Start (Pre-built Image)

A pre-built image is available on DockerHub:

**DockerHub Repository:** https://hub.docker.com/r/cwulfman01/barnacle

```bash
# Pull the latest image
docker pull cwulfman01/barnacle:latest

# Or pull a specific version
docker pull cwulfman01/barnacle:v0.1.0
```

## Architecture Notes

The Tufts HPC cluster runs on Intel/AMD processors (linux/amd64). If building on Apple Silicon (M1/M2/M3), you must specify the target platform to ensure compatibility:

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

# Tag for DockerHub
docker build --platform linux/amd64 -t cwulfman01/barnacle:latest .
docker build --platform linux/amd64 -t cwulfman01/barnacle:v0.1.0 .
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
docker tag barnacle:latest cwulfman01/barnacle:latest

# Also tag with version number for releases
docker tag barnacle:latest cwulfman01/barnacle:v0.1.0
```

### Step 3: Push to DockerHub

```bash
docker push cwulfman01/barnacle:latest
docker push cwulfman01/barnacle:v0.1.0
```

The push will take several minutes depending on your upload speed (image is ~2-3 GB with dependencies).

### Step 4: Verify the Upload

Check that the image is available:

```bash
# Visit in browser
https://hub.docker.com/r/cwulfman01/barnacle

# Or test pulling
docker pull cwulfman01/barnacle:latest
```

### Complete Example Workflow

```bash
# 1. Build the image
docker build --platform linux/amd64 -t barnacle:latest .

# 2. Login to DockerHub
docker login

# 3. Tag with your username
docker tag barnacle:latest cwulfman01/barnacle:latest
docker tag barnacle:latest cwulfman01/barnacle:v0.1.0

# 4. Push both tags
docker push cwulfman01/barnacle:latest
docker push cwulfman01/barnacle:v0.1.0

# 5. Verify
docker pull cwulfman01/barnacle:latest
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

## container-mod Compatibility

The barnacle container is designed to work with [container-mod](https://github.com/cea-hpc/modules-container), a tool used on HPC clusters to expose containerized applications as module commands. The barnacle executable is installed directly at `/usr/local/bin/barnacle`, making it callable without going through an entrypoint wrapper.

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

## CI/CD Integration (Optional)

To automate Docker builds and pushes with GitHub Actions, see `.github/workflows/docker-build.yml` (if configured).

## Next Steps

For deploying to the Tufts HPC cluster, see [tufts_hpc.md](tufts_hpc.md).
