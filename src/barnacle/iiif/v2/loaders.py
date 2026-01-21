"""
Loading and parsing IIIF resources.

Provides functions to load IIIF JSON from files or URLs and parse them
into Pydantic models.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import httpx

from .models import Manifest, Collection


def fetch_json(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    """
    Fetch JSON from URL.

    Parameters:
        url: HTTP(S) URL to fetch
        timeout: Request timeout in seconds

    Returns:
        Parsed JSON as dictionary

    Raises:
        httpx.HTTPError: If request fails
        json.JSONDecodeError: If response is not valid JSON
    """
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def load_json(path_or_url: str) -> dict[str, Any]:
    """
    Load JSON from file path or URL.

    Automatically detects whether input is a URL (starts with http:// or https://)
    or a filesystem path.

    Parameters:
        path_or_url: File path or URL

    Returns:
        Parsed JSON as dictionary

    Raises:
        FileNotFoundError: If file path doesn't exist
        httpx.HTTPError: If URL fetch fails
        json.JSONDecodeError: If JSON is invalid

    Example:
        >>> data = load_json("https://example.org/manifest.json")
        >>> data = load_json("/path/to/manifest.json")
    """
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return fetch_json(path_or_url)

    p = Path(path_or_url).expanduser()
    return json.loads(p.read_text(encoding="utf-8"))


def parse_manifest(data: dict[str, Any]) -> Manifest:
    """
    Parse manifest dict into Pydantic model.

    Parameters:
        data: Manifest JSON as dictionary

    Returns:
        Manifest model

    Raises:
        pydantic.ValidationError: If JSON doesn't match manifest schema

    Example:
        >>> data = load_json(url)
        >>> manifest = parse_manifest(data)
        >>> for canvas in manifest.canvases():
        ...     print(canvas.id)
    """
    return Manifest.model_validate(data)


def parse_collection(data: dict[str, Any]) -> Collection:
    """
    Parse collection dict into Pydantic model.

    Parameters:
        data: Collection JSON as dictionary

    Returns:
        Collection model

    Raises:
        pydantic.ValidationError: If JSON doesn't match collection schema

    Example:
        >>> data = load_json(url)
        >>> collection = parse_collection(data)
        >>> for manifest_id in collection.manifest_ids():
        ...     print(manifest_id)
    """
    return Collection.model_validate(data)


def load_manifest(path_or_url: str) -> Manifest:
    """
    Load and parse manifest from path or URL.

    Combines load_json() and parse_manifest() in one call.

    Parameters:
        path_or_url: File path or URL to manifest

    Returns:
        Manifest model

    Raises:
        FileNotFoundError: If file path doesn't exist
        httpx.HTTPError: If URL fetch fails
        json.JSONDecodeError: If JSON is invalid
        pydantic.ValidationError: If JSON doesn't match manifest schema

    Example:
        >>> manifest = load_manifest("https://example.org/manifest.json")
        >>> print(manifest.id)
        >>> print(len(manifest.canvases()))
    """
    data = load_json(path_or_url)
    return parse_manifest(data)


def load_collection(path_or_url: str) -> Collection:
    """
    Load and parse collection from path or URL.

    Combines load_json() and parse_collection() in one call.

    Parameters:
        path_or_url: File path or URL to collection

    Returns:
        Collection model

    Raises:
        FileNotFoundError: If file path doesn't exist
        httpx.HTTPError: If URL fetch fails
        json.JSONDecodeError: If JSON is invalid
        pydantic.ValidationError: If JSON doesn't match collection schema

    Example:
        >>> collection = load_collection("https://example.org/collection.json")
        >>> print(collection.id)
        >>> print(len(collection.manifest_ids()))
    """
    data = load_json(path_or_url)
    return parse_collection(data)
