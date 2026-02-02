# Barnacle – Development Bookmark

_Last updated: 2026-01-14_

This file records the current working state of the Barnacle project so work can
resume quickly after interruptions or context loss.

---

## ✅ Current State (What Works)

- **IIIF manifest validation**
  - Accepts both `sc:Manifest` and `sc:Collection` roots
  - Validation logic updated and committed

- **OCR pipeline**
  - Kraken OCR is working end-to-end
  - Uses **baseline segmentation** (`kraken segment --baseline`)
  - OCR produces text successfully on non-blank pages
  - Blank pages legitimately yield empty text

- **Kraken model**
  - Using local model:
    - `models/McCATMuS_nfd_nofix_V1.mlmodel`
  - DOI-based auto-download was unreliable (rate limits); local model preferred

- **Caching**
  - Page images cached under `.barnacle-cache/images`
  - Cached images dramatically reduce per-page runtime

- **Resume safety**
  - `barnacle ocr --resume` skips pages already present in output JSONL
  - Output files are **per-manifest**, named by SHA1 of manifest URL

- **Production scale awareness**
  - ~2,778 titles
  - Many titles are several hundred pages
  - Rough timing estimate: ~1 minute/page without cache

---

## 🧰 Tooling Decisions

- **Python environments**
  - Managed via `pdm`
  - Always invoke commands with `pdm run …`

- **Task runner**
  - `just` is used **only as a dispatcher**
  - Non-trivial logic lives in Python scripts
  - This avoids Justfile parsing and quoting issues

- **Scripts over shell**
  - Status reporting, batching, hashing, etc. should live in `scripts/*.py`
  - Just recipes should call those scripts directly

---

## 📂 Repo Structure (Relevant Parts)

```
src/barnacle/
  cli.py              # Main CLI
  ocr.py              # OCR backend abstraction
models/
  McCATMuS_nfd_nofix_V1.mlmodel
scripts/
  ocr_resume_status.py
docs/
  overview.md
  roadmap.md
  mvp/contracts.md
  dev-bookmark.md     # ← this file
```

---

## 🧪 Known Working Commands

```bash
# Smoke test OCR
just ocr-smoke

# Resume-safe OCR for a single manifest
just ocr-resume <manifest-url>

# Resume-safe batch run
just batch-ocr-resume manifests.txt

# Status / accounting
just ocr-resume-status
```

---

## 🚧 Known Pain Points

- `just` is sensitive to:
  - indentation
  - semicolons
  - multi-line inline scripts
- Solution: move logic to Python scripts

---

## ▶️ Next Steps (Planned)

1. **Extract full batch logic into Python**
   - `scripts/batch_ocr_resume.py`
   - Retry logic
   - Continue-on-error
   - Per-manifest timing summaries

2. **Run metadata**
   - Emit a run manifest (JSON/YAML):
     - model
     - start/end timestamps
     - git commit
     - counts

3. **Parallelization**
   - Parallelize *by manifest*, not page
   - Bounded concurrency
   - No shared output files

---

## 🧠 Design Principles (Do Not Forget)

- Prefer **clarity over cleverness**
- Prefer **Python over shell**
- Prefer **resume-safe, inspectable artifacts**
- Treat OCR as a long-running, failure-prone production process
