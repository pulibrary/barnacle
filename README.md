# Barnacle

Barnacle is a Python project for generating high-quality, machine-readable text from scanned resources exposed via IIIF, with a focus on historically complex typography (e.g., 18th-century print features such as the long *s*) and standards-based interoperability.

The initial target is the Princeton University Library Digital Collections (Figgy/DPUL) **Lapidus** collection:
`https://dpul.princeton.edu/lapidus`

Barnacle is being developed at Princeton University Library and is intended to be useful both internally (PUL workflows) and externally (e.g., collaborating researchers).

---

## Status

**Early design / MVP planning.**  
We are currently implementing the first milestone: an end-to-end pipeline that takes IIIF Presentation 2.1 manifests, extracts page images, runs OCR/ATR with Kraken, and writes corpus-friendly outputs.

---

## Motivation

PUL’s repository provides OCR for many scanned volumes, but the default OCR quality is not sufficient for certain kinds of historical print (notably typographic features and ligatures). Barnacle exists to:

- produce improved text output suitable for corpus linguistics and downstream NLP/ML work
- preserve provenance (which image produced which text, with which model/config)
- provide a clean path to attach recognized text back to IIIF resources as Web Annotations (future milestone)

---

## High-level architecture

Barnacle is organized as three layers (which may become separate packages):

1. **IIIF models**
   - Pydantic models for IIIF Presentation API resources
   - Initial support: **IIIF Presentation 2.1** (required for Figgy)
   - Planned: **IIIF Presentation 3.0** (as soon as feasible)

2. **ATR engines**
   - An `ATREngine` abstraction (`recognize(image) -> text`)
   - Initial engine: **Kraken** (configurable recognition models)
   - Planned engine: **Tesseract** (via pytesseract), plus user-defined engines

3. **Pipeline**
   - Batch runner that:
     - reads a list of manifests
     - iterates canvases/pages
     - resolves image URLs
     - runs recognition
     - writes outputs incrementally (restartable/resumable)

---

## Outputs (MVP)

The MVP will write corpus-oriented outputs suitable for analysis and handoff:

- **JSONL per volume** (one record per page)
- optional **plain-text concatenation** per volume
- stable identifiers and provenance fields (manifest URL, canvas ID, engine config hash, model DOI/name, etc.)

---

## Standards and dependencies

Barnacle is designed to integrate with (or be compatible with):

- IIIF Presentation API 2.1 and 3.0  
  https://iiif.io/api/presentation/2.1/  
  https://iiif.io/api/presentation/3.0/
- Web Annotation Data Model (planned milestone)  
  https://www.w3.org/TR/annotation-model/
- Kraken (recognition; model management via `kraken list/show/get`)  
  https://kraken.re/

---

## Development notes

- The project will begin with IIIF Presentation **2.1** models because Figgy manifests use 2.1 extensively.
- Kraken recognition must be **configurable by model**, including support for Kraken’s model installation workflow:
  - `kraken list`
  - `kraken show <doi>`
  - `kraken get <doi>`

---

## Contributing / collaboration

This project is at an early stage. If you want to collaborate:

- open an Issue describing your use case (feature request) or problem (bug)
- for design changes, please include a short rationale and any relevant examples (manifest snippets, page images, etc.)

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

