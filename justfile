# Barnacle workflow commands
# Run `just` (or `just --list`) to see available commands.

set shell := ["bash", "-eu", "-c"]

# Export these so recipes can read them as environment variables too.
set export

# ----------------------------
# Defaults (override like: MODEL=... OUT=... LOG_LEVEL=DEBUG just ocr <url> 5)
# ----------------------------

MODEL := "models/McCATMuS_nfd_nofix_V1.mlmodel"
OUT := "out.jsonl"
LOG_LEVEL := "INFO"

# Convenient default manifest for smoke tests
FIGGY_MANIFEST := "https://figgy.princeton.edu/concern/scanned_resources/22a5dd98-7a15-4ed9-bdbc-16bb4ae785b6/manifest"

# Default recipe: list commands
default:
    @just --list


#-----------------------------
# Environment
#-----------------------------

install:
    pdm install

python:
    pdm run python

shell:
    source .venv/bin/activate && exec bash


#-----------------------------
# Quality & tests
#-----------------------------

lint:
    pdm run ruff check src

format:
    pdm run ruff format src

test:
    pdm run pytest

check:
    just lint
    just test


# ----------------------------
# OCR (parameterized)
# ----------------------------

# Usage:
#   just ocr <MANIFEST_OR_COLLECTION>
#   just ocr <MANIFEST_OR_COLLECTION> 10
#   OUT=out10.jsonl just ocr <MANIFEST_OR_COLLECTION> 10
#   MODEL=models/Whatever.mlmodel LOG_LEVEL=DEBUG just ocr <MANIFEST_OR_COLLECTION> 5
ocr MANIFEST_OR_COLLECTION MAX_PAGES="2":
    pdm run barnacle ocr "{{MANIFEST_OR_COLLECTION}}" \
      --model "${MODEL}" \
      --out "${OUT}" \
      --max-pages "{{MAX_PAGES}}" \
      --log-level "${LOG_LEVEL}"

ocr-smoke:
    just ocr "${FIGGY_MANIFEST}" 2

ocr-10:
    just ocr "${FIGGY_MANIFEST}" 10

# ----------------------------
# OCR (resume-safe, production-friendly)
# ----------------------------

# Where per-manifest outputs go. Override as needed:
#   OUT_DIR=runs/ocr-2026-01-15 just ocr-resume <url>
OUT_DIR := "runs/ocr"

# Usage:
#   just ocr-resume <MANIFEST_OR_COLLECTION>
#   just ocr-resume <MANIFEST_OR_COLLECTION> 10
#
# Notes:
# - Output file is derived from the manifest URL via SHA1:
#     runs/ocr/<sha1>.jsonl
# - This plays nicely with Barnacle's built-in --resume behavior
#   (skip pages already present in the output JSONL).
ocr-resume MANIFEST_OR_COLLECTION MAX_PAGES="0":
    mkdir -p "${OUT_DIR}"
    out="${OUT_DIR}/$(pdm run python -c 'import hashlib,sys; print(hashlib.sha1(sys.argv[1].encode("utf-8")).hexdigest())' "{{MANIFEST_OR_COLLECTION}}").jsonl"; \
    if [ "{{MAX_PAGES}}" = "0" ]; then \
      pdm run barnacle ocr "{{MANIFEST_OR_COLLECTION}}" --model "${MODEL}" --out "${out}" --log-level "${LOG_LEVEL}" --resume; \
    else \
      pdm run barnacle ocr "{{MANIFEST_OR_COLLECTION}}" --model "${MODEL}" --out "${out}" --max-pages "{{MAX_PAGES}}" --log-level "${LOG_LEVEL}" --resume; \
    fi; \
    echo "Wrote/updated: ${out}"

ocr-resume-smoke:
    just ocr-resume "${FIGGY_MANIFEST}" 2

ocr-resume-10:
    just ocr-resume "${FIGGY_MANIFEST}" 10


# ----------------------------
# Batch runner (simple)
# ----------------------------

# Usage:
#   just run manifests.txt output/
#   just run manifests.txt output/ 5
run MANIFEST_LIST OUTPUT_DIR MAX_PAGES="":
    @if [ -n "{{MAX_PAGES}}" ]; then \
      pdm run barnacle run "{{MANIFEST_LIST}}" "{{OUTPUT_DIR}}" --max-pages "{{MAX_PAGES}}"; \
    else \
      pdm run barnacle run "{{MANIFEST_LIST}}" "{{OUTPUT_DIR}}"; \
    fi


# ----------------------------
# Batch runner (resume-safe)
# ----------------------------

# Usage:
#   just batch-ocr-resume manifests.txt
#   just batch-ocr-resume manifests.txt 5
#   OUT_DIR=runs/ocr-2026-01-15 LOG_LEVEL=INFO just batch-ocr-resume manifests.txt
#
# File format:
#   - one URL per line
#   - blank lines allowed
#   - lines beginning with # are ignored
batch-ocr-resume MANIFEST_LIST MAX_PAGES="0":
    bash -eu -c ' \
      list="{{MANIFEST_LIST}}"; \
      if [ ! -f "$list" ]; then echo "Manifest list not found: $list" >&2; exit 2; fi; \
      n=0; \
      while IFS= read -r line || [ -n "$line" ]; do \
        url="$line"; \
        url="${url%%#*}"; \
        url="$(printf "%s" "$url" | sed -e "s/^[[:space:]]*//" -e "s/[[:space:]]*$//")"; \
        if [ -z "$url" ]; then continue; fi; \
        n=$((n+1)); \
        echo "[$n] $url"; \
        if [ "{{MAX_PAGES}}" = "0" ]; then \
          just ocr-resume "$url"; \
        else \
          just ocr-resume "$url" "{{MAX_PAGES}}"; \
        fi; \
      done < "$list" \
    '


# ----------------------------
# Resume-run status / reporting
# ----------------------------

# Usage:
#   just ocr-resume-status
#   OUT_DIR=runs/ocr-2026-01-15 just ocr-resume-status
ocr-resume-status:
    pdm run python scripts/ocr_resume_status.py

# ----------------------------
# Profiling / timing
# ----------------------------

# Usage:
#   just time-ocr <url> 5
time-ocr MANIFEST_OR_COLLECTION MAX_PAGES="2":
    /usr/bin/time -lp pdm run barnacle ocr "{{MANIFEST_OR_COLLECTION}}" \
      --model "${MODEL}" \
      --out "${OUT}" \
      --max-pages "{{MAX_PAGES}}" \
      --log-level "${LOG_LEVEL}"

# Usage:
#   just profile-ocr <url> 5
#
# This profiles the CLI entrypoint as executed by pdm.
# (We avoid assuming `python -m barnacle.cli` or `python -m barnacle` exists.)
profile-ocr MANIFEST_OR_COLLECTION MAX_PAGES="2" PROF="profile.prof":
    pdm run python -m cProfile -o "{{PROF}}" "$(pdm run which barnacle)" ocr "{{MANIFEST_OR_COLLECTION}}" \
      --model "${MODEL}" \
      --out "${OUT}" \
      --max-pages "{{MAX_PAGES}}" \
      --log-level "${LOG_LEVEL}"

profile-open PROF="profile.prof":
    pdm run python -m snakeviz "{{PROF}}"


# ----------------------------
# Release
# ----------------------------

build:
    pdm build

release-check:
    just lint
    just test
    just build

release:
    rm -rf dist
    pdm build
    ls -lah dist


# ----------------------------
# Docs
# ----------------------------

docs-list:
    find docs -maxdepth 3 -type f -name "*.md" -print

docs-serve PORT="8008":
    cd docs && python -m http.server "{{PORT}}"

docs-open:
    open docs/overview.md
    open docs/roadmap.md
    open docs/mvp/contracts.md


# ----------------------------
# Maintenance
# ----------------------------

clean-cache:
    rm -rf .barnacle-cache

clean:
    rm -rf .barnacle-cache out.jsonl

clean-all:
    rm -rf .barnacle-cache out.jsonl dist
