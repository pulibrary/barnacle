"""
IIIF Presentation 2.1 models and utilities.

This module provides Pydantic models for IIIF Presentation API 2.1 resources
along with loaders, validation, and traversal helpers.

Basic usage:
    >>> from barnacle.iiif.v2 import load_manifest, validate_manifest
    >>>
    >>> manifest = load_manifest("https://example.org/manifest.json")
    >>> issues = validate_manifest(manifest)
    >>> if not issues:
    ...     for canvas in manifest.canvases():
    ...         url = canvas.image_url()
    ...         print(url)

Traversing collections:
    >>> from barnacle.iiif.v2 import iter_manifests
    >>>
    >>> for manifest_id, manifest in iter_manifests(collection_url):
    ...     print(f"Processing {manifest_id}")
    ...     for canvas in manifest.canvases():
    ...         # Process each page
    ...         pass
"""

from .models import (
    Manifest,
    Collection,
    Canvas,
    Sequence,
    Annotation,
    ImageResource,
    ImageService,
)
from .loaders import (
    load_manifest,
    load_collection,
    load_json,
    parse_manifest,
    parse_collection,
    fetch_json,
)
from .validation import (
    ValidationIssue,
    validate_manifest,
    validate_collection,
    validate_canvas,
)
from .traversal import (
    iter_manifests,
    is_collection,
    is_manifest,
)

__all__ = [
    # Models
    "Manifest",
    "Collection",
    "Canvas",
    "Sequence",
    "Annotation",
    "ImageResource",
    "ImageService",
    # Loaders
    "load_manifest",
    "load_collection",
    "load_json",
    "parse_manifest",
    "parse_collection",
    "fetch_json",
    # Validation
    "ValidationIssue",
    "validate_manifest",
    "validate_collection",
    "validate_canvas",
    # Traversal
    "iter_manifests",
    "is_collection",
    "is_manifest",
]
