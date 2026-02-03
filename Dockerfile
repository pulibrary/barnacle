# Dockerfile for Barnacle OCR Pipeline
# Designed for: Docker build → DockerHub → Singularity on Tufts HPC

FROM python:3.12-slim

# Install system dependencies for Kraken OCR
RUN apt-get update && apt-get install -y \
    git \
    libvips-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml pdm.lock README.md ./
COPY src/ ./src/

# Install the package directly with pip (uses pyproject.toml)
# This places 'barnacle' in /usr/local/bin for direct execution
RUN pip install --no-cache-dir .

# Create mount points for runtime volumes
# These will be bind-mounted from HPC storage at runtime
RUN mkdir -p /models /cache /output

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Entry point: barnacle is directly available in PATH
ENTRYPOINT ["barnacle"]
CMD ["--help"]
