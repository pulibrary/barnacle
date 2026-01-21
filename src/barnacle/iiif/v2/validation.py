"""
Validation for IIIF v2 resources.

Validates IIIF manifests and collections against Barnacle's pipeline requirements.
These validators check for the minimal structure needed for OCR processing, not
full IIIF Presentation 2.1 compliance.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Manifest, Collection, Canvas


@dataclass(frozen=True)
class ValidationIssue:
    """
    Represents a validation problem.

    Attributes:
        path: JSON path to the problematic field (e.g., "sequences[0].canvases[2]")
        message: Human-readable description of the issue
    """

    path: str
    message: str


def validate_manifest(manifest: Manifest) -> list[ValidationIssue]:
    """
    Validate manifest for OCR pipeline requirements.

    Checks that the manifest has:
    - At least one sequence
    - At least one canvas
    - Each canvas has at least one image
    - Each image has an accessible IIIF Image API service

    Parameters:
        manifest: Manifest to validate

    Returns:
        List of validation issues (empty if valid)

    Example:
        >>> manifest = load_manifest(url)
        >>> issues = validate_manifest(manifest)
        >>> if issues:
        ...     for issue in issues:
        ...         print(f"{issue.path}: {issue.message}")
    """
    issues: list[ValidationIssue] = []

    if not manifest.sequences:
        issues.append(ValidationIssue("sequences", "Missing or empty sequences[]."))
        return issues

    canvas_count = 0
    for seq_i, seq in enumerate(manifest.sequences):
        for c_i, canvas in enumerate(seq.canvases):
            canvas_count += 1

            if not canvas.images:
                issues.append(
                    ValidationIssue(
                        f"sequences[{seq_i}].canvases[{c_i}].images",
                        "Canvas missing images[].",
                    )
                )
                continue

            service = canvas.primary_image_service()
            if service is None:
                issues.append(
                    ValidationIssue(
                        f"sequences[{seq_i}].canvases[{c_i}].images[0].resource.service",
                        "Image resource missing service (IIIF Image API).",
                    )
                )

    if canvas_count == 0:
        issues.append(ValidationIssue("sequences[*].canvases", "No canvases found."))

    return issues


def validate_collection(collection: Collection) -> list[ValidationIssue]:
    """
    Validate collection structure.

    Checks that the collection has:
    - At least one manifest reference
    - Each manifest reference has an @id

    Parameters:
        collection: Collection to validate

    Returns:
        List of validation issues (empty if valid)

    Example:
        >>> collection = load_collection(url)
        >>> issues = validate_collection(collection)
        >>> if issues:
        ...     print(f"Collection has {len(issues)} validation issues")
    """
    issues: list[ValidationIssue] = []

    if not collection.manifests:
        issues.append(ValidationIssue("manifests", "Empty manifests[]."))

    for i, m in enumerate(collection.manifests):
        if "@id" not in m:
            issues.append(ValidationIssue(f"manifests[{i}].@id", "Missing @id."))

    return issues


def validate_canvas(canvas: Canvas) -> list[ValidationIssue]:
    """
    Validate single canvas.

    Convenience function to validate a canvas in isolation.

    Parameters:
        canvas: Canvas to validate

    Returns:
        List of validation issues (empty if valid)
    """
    issues: list[ValidationIssue] = []

    if not canvas.images:
        issues.append(ValidationIssue("images", "Canvas missing images[]."))
        return issues

    service = canvas.primary_image_service()
    if service is None:
        issues.append(
            ValidationIssue(
                "images[0].resource.service",
                "Image resource missing service (IIIF Image API).",
            )
        )

    return issues
