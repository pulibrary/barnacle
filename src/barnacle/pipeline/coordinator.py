"""
Collection parsing and manifest list generation.

Coordinates processing of IIIF collections by generating manifest lists
suitable for SLURM job arrays or other parallel processing systems.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from barnacle.iiif.v2 import iter_manifests

from .output import manifest_output_path


@dataclass(frozen=True)
class ManifestTask:
    """
    Represents a single manifest processing task.

    Attributes:
        manifest_id: Manifest URL or identifier
        output_path: Path where OCR results should be written
    """

    manifest_id: str
    output_path: Path


def prepare_manifest_list(
    collection_or_manifest: str,
    output_dir: Path,
) -> list[ManifestTask]:
    """
    Parse collection/manifest and return list of tasks for processing.

    Takes a IIIF collection or manifest URL and generates a list of
    processing tasks, one per manifest. Each task includes the manifest
    ID and the SHA1-based output path.

    This function is designed to be called once before submitting a
    SLURM job array, to generate the manifest list file.

    Parameters:
        collection_or_manifest: URL or path to collection or manifest
        output_dir: Directory for output JSONL files

    Returns:
        List of ManifestTask objects

    Raises:
        ValueError: If resource type is unsupported
        httpx.HTTPError: If URL fetch fails
        json.JSONDecodeError: If JSON is invalid

    Example:
        >>> tasks = prepare_manifest_list(
        ...     "https://example.org/collection",
        ...     Path("runs/ocr")
        ... )
        >>> for task in tasks:
        ...     print(f"{task.manifest_id} -> {task.output_path}")
    """
    tasks: list[ManifestTask] = []

    for manifest_id, _manifest in iter_manifests(collection_or_manifest):
        output_path = manifest_output_path(manifest_id, output_dir)
        tasks.append(ManifestTask(manifest_id=manifest_id, output_path=output_path))

    return tasks


def write_manifest_list(tasks: list[ManifestTask], manifest_list_path: Path) -> None:
    """
    Write manifest tasks to a tab-separated file.

    Creates a file with one line per task:
        manifest_url<TAB>output_path

    This format is designed to be read by SLURM job arrays using sed.

    Parameters:
        tasks: List of ManifestTask objects
        manifest_list_path: Path to output file

    Example:
        >>> tasks = prepare_manifest_list(collection_url, output_dir)
        >>> write_manifest_list(tasks, Path("manifests.txt"))
    """
    manifest_list_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_list_path.open("w", encoding="utf-8") as f:
        for task in tasks:
            f.write(f"{task.manifest_id}\t{task.output_path}\n")
