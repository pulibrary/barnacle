# Barnacle

Barnacle is a Python pipeline for generating high-quality, machine-readable text from scanned resources exposed via IIIF, with a focus on historically complex typography (e.g., 18th-century print features such as the long *s*) and standards-based interoperability.

The initial target is the Princeton University Library Digital Collections (Figgy/DPUL) **Lapidus** collection:
`https://dpul.princeton.edu/lapidus`

Barnacle is being developed at Princeton University Library and is intended to be useful both internally (PUL workflows) and externally (e.g., collaborating researchers).

---

## Status

**Production-ready MVP** deployed on Tufts HPC cluster.

The pipeline processes IIIF Presentation 2.1 manifests and collections, extracts page images via IIIF Image API, runs OCR with Kraken, and writes corpus-friendly JSONL outputs with full provenance tracking.

**Deployment modes:**
- **Local testing**: CLI tool for single manifests
- **HPC production**: Docker/Singularity containers with SLURM job arrays for parallel collection processing

**Current capabilities:**
- ✅ IIIF Presentation 2.1 support (manifests and collections)
- ✅ Kraken OCR with configurable models
- ✅ Resume-safe processing (skip already-processed pages)
- ✅ Per-manifest JSONL output with provenance
- ✅ Parallel processing via SLURM job arrays
- ✅ Containerized deployment (Docker → Singularity)

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/pulibrary/barnacle.git
cd barnacle

# Install dependencies with PDM
pdm install

# Download Kraken model
pdm run kraken get 10.5281/zenodo.14585602
```

### Basic Usage

```bash
# Validate a manifest
pdm run barnacle validate <MANIFEST_URL>

# Run OCR on a single manifest (local testing)
pdm run barnacle ocr <MANIFEST_URL> \
    --model 10.5281/zenodo.14585602 \
    --out output.jsonl \
    --max-pages 10

# Run OCR on multiple manifests (batch processing)
pdm run barnacle run manifests.txt output/ --max-pages 5

# Sample IIIF image URL from manifest
pdm run barnacle sample-image-url <MANIFEST_URL>
```

### HPC Deployment

For production processing on HPC clusters with SLURM:

```bash
# Build Docker image
docker build -t barnacle:latest .

# Push to DockerHub
docker push yourusername/barnacle:latest

# On HPC: Convert to Singularity
singularity pull barnacle.sif docker://yourusername/barnacle:latest

# Process collection in parallel
./slurm/run_collection.sh <COLLECTION_URL> lapidus_batch
```

See [`docs/docker.md`](docs/docker.md) and [`docs/slurm.md`](docs/slurm.md) for detailed deployment instructions.

---

## Motivation

PUL's repository provides OCR for many scanned volumes, but the default OCR quality is not sufficient for certain kinds of historical print (notably typographic features and ligatures). Barnacle exists to:

- produce improved text output suitable for corpus linguistics and downstream NLP/ML work
- preserve provenance (which image produced which text, with which model/config)
- provide a clean path to attach recognized text back to IIIF resources as Web Annotations (future milestone)

---

## Architecture

Barnacle is organized as modular Python packages with clear separation of concerns:

### Core Modules

1. **`barnacle.iiif.v2`** - IIIF Presentation 2.1 support
   - Type-safe Pydantic models (`Manifest`, `Collection`, `Canvas`, `ImageService`)
   - Loaders for files and URLs (`load_manifest`, `load_collection`)
   - Validation for pipeline requirements (`validate_manifest`, `validate_collection`)
   - Traversal helpers (`iter_manifests` for collections)

2. **`barnacle.ocr`** - OCR engine abstraction
   - `KrakenBackend` with configurable models
   - Automatic model installation from DOIs
   - Support for custom model paths

3. **`barnacle.pipeline`** - Processing logic
   - `coordinator.py`: Collection parsing, manifest list generation
   - `worker.py`: Single manifest processing (SLURM-compatible)
   - `output.py`: SHA1-based output paths, resume tracking

4. **`barnacle.cli`** - Command-line interface
   - `validate`: Validate manifests/collections
   - `ocr`: Run OCR locally or on single manifests
   - `run`: Process multiple manifests from a list file
   - `sample-image-url`: Extract IIIF image URLs

### Deployment Architecture

```
Collection URL or CSV file
    ↓
Coordinator: Parse collection/CSV → manifest list (TSV)
    ↓
SLURM Job Array: N parallel workers
    ├─ Worker 1: process_manifest() → SHA1_1.jsonl
    ├─ Worker 2: process_manifest() → SHA1_2.jsonl
    └─ Worker N: process_manifest() → SHA1_N.jsonl
```

**Input sources:**
- IIIF Collection URL: Automatically traverses and extracts manifest URLs
- CSV file (`--csv` flag): Reads pre-extracted manifest URLs from `manifest_url` column

**Key design decisions:**
- **Per-manifest output files** (SHA1-named): Enables parallel processing without file contention
- **Resume safety**: Page-level tracking via `page_key` allows interrupted jobs to resume
- **SLURM-native**: Uses job arrays for cluster-native parallelism and fault tolerance
- **Containerized**: Docker images converted to Singularity for HPC deployment

---

## Output Format

Barnacle writes **JSONL files** (one record per page) with comprehensive provenance:

```jsonl
{
  "created_at": "2026-01-22T12:34:56.789Z",
  "page_key": "https://...|canvas_id|model|jpg|!3000,3000|default|full|0",
  "canvas_index": 0,
  "engine": "kraken",
  "model": {"ref": "10.5281/zenodo.14585602", "resolved": "/path/to/model.mlmodel"},
  "manifest_url": "https://example.org/manifest",
  "canvas_id": "https://example.org/canvas/1",
  "image_url": "https://iiif.example.org/image1/full/!3000,3000/0/default.jpg",
  "elapsed_ms": 1234,
  "text": "Recognized text content...",
  "source_metadata_id": "optional_csv_field",
  "ark": "optional_ark_identifier"
}
```

**Key fields:**
- `page_key`: Stable identifier for resume/deduplication (manifest + canvas + model + IIIF params)
- `text`: Full OCR text for the page
- `model`: Both user-provided reference (DOI) and resolved path
- `elapsed_ms`: Processing time for performance tracking

**Output file naming:**
- Single manifest: User-specified path (e.g., `output.jsonl`)
- Collection processing: SHA1-based per-manifest files (e.g., `<sha1_of_manifest_url>.jsonl`)

---

## Documentation

- **[Docker Deployment Guide](docs/docker.md)**: Building containers, testing locally, pushing to DockerHub
- **[SLURM Deployment Guide](docs/slurm.md)**: HPC cluster deployment, job arrays, monitoring
- **[Batch Processing Guide](docs/batch-processing.md)**: GNU Parallel for non-HPC environments (VMs, workstations)
- **[Deployment Plan](docs/deployment-plan.md)**: Full architecture design and production roadmap
- **[Tests](tests/)**: Comprehensive test suite with fixtures

---

## Standards and Dependencies

Barnacle integrates with:

- **IIIF Presentation API 2.1**: Manifest/Collection parsing and validation
  https://iiif.io/api/presentation/2.1/
- **IIIF Image API 2.1**: Image URL construction and parameter handling
  https://iiif.io/api/image/2.1/
- **Kraken**: OCR/ATR engine with model management
  https://kraken.re/
- **Pydantic**: Type-safe data models and validation
  https://docs.pydantic.dev/
- **PDM**: Python package and dependency management
  https://pdm-project.org/

**Planned:**
- IIIF Presentation API 3.0 support
- Web Annotation output format
- Additional OCR engines (Tesseract, etc.)

---

## Development Setup

### Prerequisites

- Python 3.12+
- PDM (Python package manager)
- libvips (for Kraken image processing)

### Setup

```bash
# Install PDM
pip install pdm

# Clone repository
git clone https://github.com/pulibrary/barnacle.git
cd barnacle

# Install dependencies
pdm install

# Install Kraken model
pdm run kraken get 10.5281/zenodo.14585602
```

### Running Tests

```bash
# Run all tests
pdm run pytest

# Run with coverage
pdm run pytest --cov=barnacle --cov-report=html

# Run specific test file
pdm run pytest tests/test_iiif_models.py
```

### Using just

Barnacle includes a `justfile` with common workflow commands. Install [just](https://github.com/casey/just) and run `just` to see available recipes:

```bash
# Install just (macOS)
brew install just

# Install just (Ubuntu/Debian)
sudo apt install just

# List all available commands
just

# Common commands
just test           # Run tests
just lint           # Run linter
just check          # Run lint + tests
just ocr-smoke      # Quick OCR test (2 pages)
just run manifests.txt output/  # Batch process manifests
```

Run `just --list` to see all available recipes with descriptions.

### Code Structure

```
barnacle/
├── src/barnacle/
│   ├── iiif/v2/          # IIIF Presentation 2.1 models
│   ├── pipeline/         # Processing logic
│   ├── ocr.py            # OCR engine abstraction
│   └── cli.py            # Command-line interface
├── tests/                # Test suite with fixtures
├── slurm/                # SLURM job scripts
├── scripts/              # Utility scripts
├── docs/                 # Documentation
├── Dockerfile            # Container definition
└── pyproject.toml        # Project configuration
```

---

## Contributing

Contributions are welcome! Please:

1. **Open an issue** to discuss new features or report bugs
2. **Include context**: For bugs, provide manifest URLs or test cases; for features, explain the use case
3. **Write tests**: All new features should include tests in `tests/`
4. **Follow code style**: Use type hints and docstrings
5. **Update documentation**: Update relevant docs in `docs/` if needed

### Reporting Issues

- **Bugs**: Include manifest URL, command used, error output, and expected behavior
- **Feature requests**: Describe the use case and provide examples (manifest snippets, expected output format, etc.)
- **HPC deployment issues**: Include cluster details (SLURM version, Singularity version, storage configuration)

---

## Roadmap

Future enhancements under consideration:

- **IIIF Presentation 3.0** support
- **Web Annotation** output format for attaching OCR to IIIF Canvases
- **Additional OCR engines**: Tesseract, custom engines
- **Post-processing**: Text normalization, dehyphenation, ligature expansion
- **Quality metrics**: Confidence scores, validation against ground truth
- **API server**: RESTful API for on-demand OCR
- **Cloud deployment**: Kubernetes/container orchestration beyond SLURM

See [GitHub Issues](https://github.com/pulibrary/barnacle/issues) for active discussions.

---

## Acknowledgments

- **Tufts HPC cluster** team for deployment support and infrastructure
- **Kraken** developers for the OCR engine and model ecosystem
- **IIIF community** for standards and best practices
- **McCATMuS** project for historical print recognition models

---

## License

Copyright 2024–2025 Princeton University Library
Additional copyright may be held by others, as reflected in the commit log.

Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this file except in compliance with the License. You may obtain a copy of the
License at:

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

