# Roadmap

This roadmap is milestone-oriented. Issues track the actionable work.

## Milestone 1: MVP corpus builder (Lapidus / IIIF 2.1 / Kraken)
**Goal:** process a representative subset of Lapidus volumes end-to-end with improved OCR suitable for corpus work.

Deliverables:
- IIIF Presentation 2.1 “core traversal” models + helpers
- KrakenEngine (configurable models; DOI-based install support)
- Batch runner: CSV → manifests → canvases → OCR → outputs
- Output format: JSONL per page (+ optional per-volume plain text)
- Resumability and caching (results and/or images)

Exit criteria:
- Run completes on a pilot set (e.g., 10–20 volumes) without manual intervention
- Outputs contain sufficient provenance to reproduce a run
- OCR quality demonstrably improves over Figgy baseline for key typographic features (e.g., long *s*)

## Milestone 2: Expand IIIF + improve text structure
- Expand IIIF 2.1 model coverage beyond traversal subset
- Optional structured OCR output capture (lines/regions/confidence)
- Better corpus packaging and metadata enrichment (as needed for analysis)

## Milestone 3: Web Annotation export
- Web Annotation model(s) + serialization
- Mapping of OCR results onto canvases (targets/selectors)
- Export suitable for ingestion into an annotation server (e.g., miiify)

## Milestone 4: IIIF Presentation 3 support
- Versioned v3 models (`barnacle_iiif.v3`)
- Migration/adaptation story for v2 vs v3 usage
