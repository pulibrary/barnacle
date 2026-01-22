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

# Install PDM and project dependencies
RUN pip install --no-cache-dir pdm && \
    pdm install --prod --no-editable

# Create mount points for runtime volumes
# These will be bind-mounted from HPC storage at runtime
RUN mkdir -p /models /cache /output

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Entry point: Use PDM to run barnacle commands
ENTRYPOINT ["pdm", "run", "barnacle"]
CMD ["--help"]
