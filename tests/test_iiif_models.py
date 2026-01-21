"""Tests for IIIF v2 Pydantic models."""

from pathlib import Path
import pytest

from barnacle.iiif.v2 import (
    Manifest,
    Collection,
    Canvas,
    ImageService,
    parse_manifest,
    parse_collection,
    load_json,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestImageService:
    """Tests for ImageService model."""

    def test_image_url_default_params(self):
        """Test IIIF Image API URL generation with defaults."""
        service = ImageService(id="https://iiif.example.org/image1")
        url = service.image_url()
        assert url == "https://iiif.example.org/image1/full/!3000,3000/0/default.jpg"

    def test_image_url_custom_params(self):
        """Test IIIF Image API URL generation with custom parameters."""
        service = ImageService(id="https://iiif.example.org/image1")
        url = service.image_url(size="200,200", fmt="png", quality="color")
        assert url == "https://iiif.example.org/image1/full/200,200/0/color.png"

    def test_image_url_strips_trailing_slash(self):
        """Test that trailing slash in service ID is handled correctly."""
        service = ImageService(id="https://iiif.example.org/image1/")
        url = service.image_url()
        assert url == "https://iiif.example.org/image1/full/!3000,3000/0/default.jpg"


class TestManifest:
    """Tests for Manifest model."""

    def test_parse_simple_manifest(self):
        """Test parsing a simple valid manifest."""
        data = load_json(str(FIXTURES_DIR / "manifest_simple.json"))
        manifest = parse_manifest(data)

        assert manifest.id == "https://example.org/manifest/simple"
        assert manifest.type == "sc:Manifest"
        assert manifest.label == "Simple Test Manifest"

    def test_manifest_canvases(self):
        """Test manifest.canvases() returns all canvases in order."""
        data = load_json(str(FIXTURES_DIR / "manifest_simple.json"))
        manifest = parse_manifest(data)

        canvases = manifest.canvases()
        assert len(canvases) == 2
        assert canvases[0].id == "https://example.org/canvas/1"
        assert canvases[1].id == "https://example.org/canvas/2"

    def test_manifest_metadata(self):
        """Test manifest metadata is parsed correctly."""
        data = load_json(str(FIXTURES_DIR / "manifest_simple.json"))
        manifest = parse_manifest(data)

        assert manifest.metadata is not None
        assert len(manifest.metadata) == 1
        assert manifest.metadata[0]["label"] == "Title"


class TestCanvas:
    """Tests for Canvas model."""

    def test_canvas_primary_image_service(self):
        """Test canvas.primary_image_service() returns first service."""
        data = load_json(str(FIXTURES_DIR / "manifest_simple.json"))
        manifest = parse_manifest(data)

        canvas = manifest.canvases()[0]
        service = canvas.primary_image_service()

        assert service is not None
        assert service.id == "https://iiif.example.org/image1"

    def test_canvas_image_url(self):
        """Test canvas.image_url() generates correct IIIF URL."""
        data = load_json(str(FIXTURES_DIR / "manifest_simple.json"))
        manifest = parse_manifest(data)

        canvas = manifest.canvases()[0]
        url = canvas.image_url(size="!1000,1000", fmt="jpg")

        assert url is not None
        assert "iiif.example.org/image1" in url
        assert "!1000,1000" in url
        assert url.endswith(".jpg")

    def test_canvas_without_service_returns_none(self):
        """Test canvas without image service returns None."""
        data = load_json(str(FIXTURES_DIR / "manifest_invalid.json"))
        manifest = parse_manifest(data)

        canvas = manifest.canvases()[0]
        service = canvas.primary_image_service()
        assert service is None

        url = canvas.image_url()
        assert url is None


class TestCollection:
    """Tests for Collection model."""

    def test_parse_simple_collection(self):
        """Test parsing a simple valid collection."""
        data = load_json(str(FIXTURES_DIR / "collection_simple.json"))
        collection = parse_collection(data)

        assert collection.id == "https://example.org/collection/simple"
        assert collection.type == "sc:Collection"
        assert collection.label == "Simple Test Collection"

    def test_collection_manifest_ids(self):
        """Test collection.manifest_ids() extracts all manifest URLs."""
        data = load_json(str(FIXTURES_DIR / "collection_simple.json"))
        collection = parse_collection(data)

        manifest_ids = collection.manifest_ids()
        assert len(manifest_ids) == 2
        assert "https://example.org/manifest/1" in manifest_ids
        assert "https://example.org/manifest/2" in manifest_ids

    def test_collection_empty_manifests(self):
        """Test collection with no manifests returns empty list."""
        collection = Collection(
            id="https://example.org/collection/empty",
            type="sc:Collection",
            manifests=[]
        )
        assert collection.manifest_ids() == []


class TestPydanticValidation:
    """Tests for Pydantic validation behavior."""

    def test_manifest_requires_id(self):
        """Test that manifest requires @id field."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            Manifest(type="sc:Manifest")

    def test_manifest_requires_type(self):
        """Test that manifest requires @type field."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            Manifest(id="https://example.org/manifest")

    def test_canvas_requires_id(self):
        """Test that canvas requires @id field."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            Canvas(type="sc:Canvas")
