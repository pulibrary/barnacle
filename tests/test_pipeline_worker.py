"""Tests for pipeline worker clear_cache_after behaviour."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call
import json
import tempfile

import pytest

from barnacle.pipeline.worker import process_manifest


def _make_canvas(image_url: str, canvas_id: str) -> MagicMock:
    canvas = MagicMock()
    canvas.id = canvas_id
    canvas.image_url.return_value = image_url
    return canvas


def _make_manifest(canvases: list) -> MagicMock:
    manifest = MagicMock()
    manifest.canvases.return_value = canvases
    return manifest


class TestClearCacheAfter:
    """Tests for the clear_cache_after parameter of process_manifest."""

    def _run_with_mocks(self, tmp_path: Path, clear_cache_after: bool) -> tuple:
        """
        Run process_manifest with all heavy dependencies mocked.

        Returns (result, unlink_calls, img_paths).
        """
        cache_dir = tmp_path / "cache"
        output_path = tmp_path / "out.jsonl"

        image_urls = [
            "https://example.org/iiif/image/1/full/!3000,3000/0/default.jpg",
            "https://example.org/iiif/image/2/full/!3000,3000/0/default.jpg",
        ]
        canvas_ids = [
            "https://example.org/canvas/1",
            "https://example.org/canvas/2",
        ]
        canvases = [_make_canvas(url, cid) for url, cid in zip(image_urls, canvas_ids)]

        unlink_calls: list[Path] = []

        with (
            patch("barnacle.pipeline.worker.KrakenBackend") as MockBackend,
            patch("barnacle.pipeline.worker.load_manifest") as mock_load,
            patch("barnacle.pipeline.worker.validate_manifest", return_value=[]),
            patch("barnacle.pipeline.worker.fetch_bytes", return_value=b"fake-image-data"),
            patch("barnacle.pipeline.worker.append_record"),
        ):
            backend = MockBackend.return_value
            backend.resolve_model.return_value = "resolved-model"
            backend.ocr_image.return_value = "OCR text"
            backend.name = "kraken"

            mock_load.return_value = _make_manifest(canvases)

            # Intercept Path.unlink via monkeypatching the specific img_path instances.
            # We do this by pre-creating the cache files so the worker skips download,
            # then patching Path.unlink on those paths.
            img_cache = cache_dir / "images"
            img_cache.mkdir(parents=True, exist_ok=True)

            import hashlib
            created_paths: list[Path] = []
            for url in image_urls:
                key = hashlib.sha1(url.encode()).hexdigest()
                p = img_cache / f"{key}.jpg"
                p.write_bytes(b"fake-image-data")
                created_paths.append(p)

            original_unlink = Path.unlink

            def tracking_unlink(self, missing_ok=False):
                unlink_calls.append(self)
                original_unlink(self, missing_ok=missing_ok)

            with patch.object(Path, "unlink", tracking_unlink):
                result = process_manifest(
                    manifest_id="https://example.org/manifest",
                    output_path=output_path,
                    model="some-model",
                    cache_dir=cache_dir,
                    resume=False,
                    clear_cache_after=clear_cache_after,
                )

        return result, unlink_calls, created_paths

    def test_images_deleted_when_clear_cache_after_true(self, tmp_path):
        result, unlink_calls, img_paths = self._run_with_mocks(tmp_path, clear_cache_after=True)

        assert result.success is True
        assert result.pages_processed == 2

        # Each img_path should have been unlinked exactly once
        assert len(unlink_calls) == 2
        for p in img_paths:
            assert p in unlink_calls

    def test_images_not_deleted_when_clear_cache_after_false(self, tmp_path):
        result, unlink_calls, img_paths = self._run_with_mocks(tmp_path, clear_cache_after=False)

        assert result.success is True
        assert result.pages_processed == 2
        assert unlink_calls == []

    def test_images_not_deleted_on_default(self, tmp_path):
        """Default behaviour (no clear_cache_after) leaves images intact."""
        cache_dir = tmp_path / "cache"
        output_path = tmp_path / "out.jsonl"

        canvases = [_make_canvas(
            "https://example.org/iiif/image/1/full/!3000,3000/0/default.jpg",
            "https://example.org/canvas/1",
        )]

        with (
            patch("barnacle.pipeline.worker.KrakenBackend") as MockBackend,
            patch("barnacle.pipeline.worker.load_manifest") as mock_load,
            patch("barnacle.pipeline.worker.validate_manifest", return_value=[]),
            patch("barnacle.pipeline.worker.fetch_bytes", return_value=b"data"),
            patch("barnacle.pipeline.worker.append_record"),
        ):
            backend = MockBackend.return_value
            backend.resolve_model.return_value = "model"
            backend.ocr_image.return_value = "text"
            backend.name = "kraken"
            mock_load.return_value = _make_manifest(canvases)

            img_cache = cache_dir / "images"
            img_cache.mkdir(parents=True, exist_ok=True)
            import hashlib
            url = "https://example.org/iiif/image/1/full/!3000,3000/0/default.jpg"
            key = hashlib.sha1(url.encode()).hexdigest()
            img_file = img_cache / f"{key}.jpg"
            img_file.write_bytes(b"data")

            # process_manifest with no clear_cache_after argument
            result = process_manifest(
                manifest_id="https://example.org/manifest",
                output_path=output_path,
                model="some-model",
                cache_dir=cache_dir,
                resume=False,
            )

        assert result.success is True
        assert img_file.exists(), "Image should still exist when clear_cache_after is not set"
