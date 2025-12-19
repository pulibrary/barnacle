# Barnacle overview

Barnacle is a Python project for producing high-quality machine-readable text from scanned resources exposed via IIIF, with an initial focus on 18th-century print and the Lapidus collection in DPUL.

Barnacle is designed as three layers:

1. **IIIF models**
   - Pydantic models for IIIF Presentation resources
   - MVP: IIIF Presentation 2.1 (Figgy manifests)
   - Planned: IIIF Presentation 3.0

2. **ATR engines**
   - Abstract `ATREngine` with `recognize(image) -> text`
   - MVP: Kraken engine, configurable by recognition model
   - Planned: Tesseract engine and user-defined engines

3. **Pipeline**
   - Reads a manifest list, resolves images per canvas, runs recognition, and writes corpus outputs
   - Designed to be resumable and provenance-preserving

Key long-term goal: enable attaching OCR output to scanned resources as Web Annotations for ingestion by annotation servers.
