"""
High-level traversal for IIIF v2 resources.

Provides convenience functions for iterating through manifests in collections
and handling both manifests and collections uniformly.
"""

from __future__ import annotations

from typing import Iterable

from .loaders import load_json, parse_manifest, parse_collection
from .models import Manifest


def iter_manifests(path_or_url: str) -> Iterable[tuple[str, Manifest]]:
    """
    Yield (manifest_id, Manifest) pairs.

    Handles both single manifests and collections uniformly:
    - If root is a Manifest: yields that one manifest
    - If root is a Collection: yields each referenced manifest

    Parameters:
        path_or_url: File path or URL to manifest or collection

    Yields:
        Tuples of (manifest_id, Manifest)

    Raises:
        ValueError: If root @type is neither sc:Manifest nor sc:Collection
        httpx.HTTPError: If URL fetch fails
        json.JSONDecodeError: If JSON is invalid
        pydantic.ValidationError: If JSON doesn't match schema

    Example:
        >>> for manifest_id, manifest in iter_manifests(collection_url):
        ...     print(f"{manifest_id}: {len(manifest.canvases())} pages")
    """
    data = load_json(path_or_url)
    root_type = data.get("@type")

    if root_type == "sc:Manifest":
        manifest = parse_manifest(data)
        yield (manifest.id, manifest)
        return

    if root_type == "sc:Collection":
        collection = parse_collection(data)
        for manifest_id in collection.manifest_ids():
            manifest_data = load_json(manifest_id)
            manifest = parse_manifest(manifest_data)
            yield (manifest_id, manifest)
        return

    raise ValueError(f"Unexpected root @type: {root_type}")


def is_collection(path_or_url: str) -> bool:
    """
    Check if resource is a Collection.

    Loads only the root JSON to check @type, without parsing the full structure.

    Parameters:
        path_or_url: File path or URL to IIIF resource

    Returns:
        True if resource is sc:Collection, False otherwise

    Raises:
        httpx.HTTPError: If URL fetch fails
        json.JSONDecodeError: If JSON is invalid

    Example:
        >>> if is_collection(url):
        ...     collection = load_collection(url)
        ... else:
        ...     manifest = load_manifest(url)
    """
    data = load_json(path_or_url)
    return data.get("@type") == "sc:Collection"


def is_manifest(path_or_url: str) -> bool:
    """
    Check if resource is a Manifest.

    Loads only the root JSON to check @type, without parsing the full structure.

    Parameters:
        path_or_url: File path or URL to IIIF resource

    Returns:
        True if resource is sc:Manifest, False otherwise

    Raises:
        httpx.HTTPError: If URL fetch fails
        json.JSONDecodeError: If JSON is invalid

    Example:
        >>> if is_manifest(url):
        ...     manifest = load_manifest(url)
        ... else:
        ...     collection = load_collection(url)
    """
    data = load_json(path_or_url)
    return data.get("@type") == "sc:Manifest"
