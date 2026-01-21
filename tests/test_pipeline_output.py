"""Tests for pipeline output utilities."""

from pathlib import Path
import tempfile
import json

from barnacle.pipeline.output import (
    manifest_output_path,
    page_key,
    load_processed_keys,
    append_record,
)


class TestManifestOutputPath:
    """Tests for manifest_output_path() function."""

    def test_generates_sha1_based_path(self):
        """Test that output path uses SHA1 hash of manifest ID."""
        manifest_id = "https://example.org/manifest/123"
        output_dir = Path("/tmp/ocr")

        path = manifest_output_path(manifest_id, output_dir)

        assert path.parent == output_dir
        assert path.suffix == ".jsonl"
        # SHA1 hash is 40 hex characters
        assert len(path.stem) == 40

    def test_same_manifest_id_produces_same_path(self):
        """Test deterministic output paths."""
        manifest_id = "https://example.org/manifest/123"
        output_dir = Path("/tmp/ocr")

        path1 = manifest_output_path(manifest_id, output_dir)
        path2 = manifest_output_path(manifest_id, output_dir)

        assert path1 == path2

    def test_different_manifest_ids_produce_different_paths(self):
        """Test that different manifests get different output files."""
        output_dir = Path("/tmp/ocr")

        path1 = manifest_output_path("https://example.org/manifest/1", output_dir)
        path2 = manifest_output_path("https://example.org/manifest/2", output_dir)

        assert path1 != path2


class TestPageKey:
    """Tests for page_key() function."""

    def test_page_key_format(self):
        """Test that page key has correct format."""
        key = page_key(
            manifest_id="https://example.org/manifest",
            canvas_id="https://example.org/canvas/1",
            model="kraken_model",
            fmt="jpg",
            size="!3000,3000",
            quality="default",
            region="full",
            rotation="0"
        )

        # Should be pipe-separated
        assert "|" in key
        # Should contain all components
        assert "https://example.org/manifest" in key
        assert "https://example.org/canvas/1" in key
        assert "kraken_model" in key

    def test_page_key_deterministic(self):
        """Test that page key is deterministic."""
        params = {
            "manifest_id": "https://example.org/manifest",
            "canvas_id": "https://example.org/canvas/1",
            "model": "model.mlmodel",
            "fmt": "jpg",
            "size": "!3000,3000",
            "quality": "default",
            "region": "full",
            "rotation": "0"
        }

        key1 = page_key(**params)
        key2 = page_key(**params)

        assert key1 == key2

    def test_different_params_produce_different_keys(self):
        """Test that different parameters produce different keys."""
        base_params = {
            "manifest_id": "https://example.org/manifest",
            "canvas_id": "https://example.org/canvas/1",
            "model": "model.mlmodel",
            "fmt": "jpg",
            "size": "!3000,3000",
            "quality": "default",
            "region": "full",
            "rotation": "0"
        }

        key1 = page_key(**base_params)
        key2 = page_key(**{**base_params, "canvas_id": "https://example.org/canvas/2"})
        key3 = page_key(**{**base_params, "size": "!2000,2000"})

        assert key1 != key2
        assert key1 != key3
        assert key2 != key3


class TestLoadProcessedKeys:
    """Tests for load_processed_keys() function."""

    def test_load_from_nonexistent_file(self):
        """Test that loading from nonexistent file returns empty set."""
        nonexistent = Path("/tmp/does_not_exist_12345.jsonl")
        processed = load_processed_keys(nonexistent)
        assert processed == set()

    def test_load_from_empty_file(self):
        """Test that loading from empty file returns empty set."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = Path(f.name)

        try:
            processed = load_processed_keys(temp_path)
            assert processed == set()
        finally:
            temp_path.unlink()

    def test_load_from_file_with_records(self):
        """Test loading page keys from JSONL file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            # Write some test records
            json.dump({"page_key": "key1", "text": "..."}, f)
            f.write("\n")
            json.dump({"page_key": "key2", "text": "..."}, f)
            f.write("\n")
            json.dump({"page_key": "key3", "text": "..."}, f)
            f.write("\n")
            temp_path = Path(f.name)

        try:
            processed = load_processed_keys(temp_path)
            assert len(processed) == 3
            assert "key1" in processed
            assert "key2" in processed
            assert "key3" in processed
        finally:
            temp_path.unlink()

    def test_load_ignores_invalid_lines(self):
        """Test that invalid JSON lines are ignored."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            json.dump({"page_key": "key1"}, f)
            f.write("\n")
            f.write("invalid json line\n")
            json.dump({"page_key": "key2"}, f)
            f.write("\n")
            temp_path = Path(f.name)

        try:
            processed = load_processed_keys(temp_path)
            assert len(processed) == 2
            assert "key1" in processed
            assert "key2" in processed
        finally:
            temp_path.unlink()

    def test_load_ignores_records_without_page_key(self):
        """Test that records without page_key field are ignored."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            json.dump({"page_key": "key1"}, f)
            f.write("\n")
            json.dump({"text": "no key here"}, f)
            f.write("\n")
            json.dump({"page_key": "key2"}, f)
            f.write("\n")
            temp_path = Path(f.name)

        try:
            processed = load_processed_keys(temp_path)
            assert len(processed) == 2
            assert "key1" in processed
            assert "key2" in processed
        finally:
            temp_path.unlink()


class TestAppendRecord:
    """Tests for append_record() function."""

    def test_append_record_creates_file(self):
        """Test that append_record creates file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.jsonl"
            record = {"page_key": "test_key", "text": "test text"}

            append_record(output_path, record)

            assert output_path.exists()

    def test_append_record_creates_parent_dirs(self):
        """Test that append_record creates parent directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "output.jsonl"
            record = {"page_key": "test_key"}

            append_record(output_path, record)

            assert output_path.exists()
            assert output_path.parent.exists()

    def test_append_record_writes_json(self):
        """Test that append_record writes valid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = Path(f.name)

        try:
            record = {"page_key": "test_key", "text": "test text", "number": 42}
            append_record(temp_path, record)

            # Read and parse the JSON
            with temp_path.open() as f:
                line = f.readline().strip()
                parsed = json.loads(line)

            assert parsed == record
        finally:
            temp_path.unlink()

    def test_append_record_appends_not_overwrites(self):
        """Test that append_record appends to existing file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Append multiple records
            append_record(temp_path, {"page_key": "key1"})
            append_record(temp_path, {"page_key": "key2"})
            append_record(temp_path, {"page_key": "key3"})

            # Read all lines
            with temp_path.open() as f:
                lines = f.readlines()

            assert len(lines) == 3
            assert json.loads(lines[0])["page_key"] == "key1"
            assert json.loads(lines[1])["page_key"] == "key2"
            assert json.loads(lines[2])["page_key"] == "key3"
        finally:
            temp_path.unlink()
