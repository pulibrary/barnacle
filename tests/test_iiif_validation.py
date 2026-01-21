"""Tests for IIIF v2 validation."""

from pathlib import Path

from barnacle.iiif.v2 import (
    validate_manifest,
    validate_collection,
    validate_canvas,
    load_json,
    parse_manifest,
    parse_collection,
)


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestManifestValidation:
    """Tests for manifest validation."""

    def test_valid_manifest_passes(self):
        """Test that a valid manifest passes validation."""
        data = load_json(str(FIXTURES_DIR / "manifest_simple.json"))
        manifest = parse_manifest(data)
        issues = validate_manifest(manifest)
        assert len(issues) == 0

    def test_invalid_manifest_missing_service(self):
        """Test that manifest missing image service fails validation."""
        data = load_json(str(FIXTURES_DIR / "manifest_invalid.json"))
        manifest = parse_manifest(data)
        issues = validate_manifest(manifest)

        assert len(issues) > 0
        # Should report missing service
        assert any("service" in issue.path.lower() for issue in issues)

    def test_manifest_without_sequences_fails(self):
        """Test that manifest without sequences fails validation."""
        manifest = parse_manifest({
            "@id": "https://example.org/manifest/empty",
            "@type": "sc:Manifest",
            "label": "Empty Manifest",
            "sequences": []
        })
        issues = validate_manifest(manifest)

        assert len(issues) > 0
        assert any("sequences" in issue.path for issue in issues)

    def test_manifest_without_canvases_fails(self):
        """Test that manifest with empty sequences fails validation."""
        manifest = parse_manifest({
            "@id": "https://example.org/manifest/nocanvases",
            "@type": "sc:Manifest",
            "label": "No Canvases",
            "sequences": [
                {
                    "@type": "sc:Sequence",
                    "canvases": []
                }
            ]
        })
        issues = validate_manifest(manifest)

        assert len(issues) > 0
        assert any("canvases" in issue.path.lower() for issue in issues)


class TestCollectionValidation:
    """Tests for collection validation."""

    def test_valid_collection_passes(self):
        """Test that a valid collection passes validation."""
        data = load_json(str(FIXTURES_DIR / "collection_simple.json"))
        collection = parse_collection(data)
        issues = validate_collection(collection)
        assert len(issues) == 0

    def test_collection_without_manifests_fails(self):
        """Test that collection without manifests fails validation."""
        collection = parse_collection({
            "@id": "https://example.org/collection/empty",
            "@type": "sc:Collection",
            "label": "Empty Collection",
            "manifests": []
        })
        issues = validate_collection(collection)

        assert len(issues) > 0
        assert any("manifests" in issue.path for issue in issues)

    def test_collection_manifest_without_id_fails(self):
        """Test that manifest reference without @id fails validation."""
        collection = parse_collection({
            "@id": "https://example.org/collection/bad",
            "@type": "sc:Collection",
            "manifests": [
                {"label": "Missing ID"}
            ]
        })
        issues = validate_collection(collection)

        assert len(issues) > 0
        assert any("@id" in issue.path for issue in issues)


class TestCanvasValidation:
    """Tests for canvas validation."""

    def test_valid_canvas_passes(self):
        """Test that a valid canvas passes validation."""
        data = load_json(str(FIXTURES_DIR / "manifest_simple.json"))
        manifest = parse_manifest(data)
        canvas = manifest.canvases()[0]

        issues = validate_canvas(canvas)
        assert len(issues) == 0

    def test_canvas_without_images_fails(self):
        """Test that canvas without images fails validation."""
        from barnacle.iiif.v2.models import Canvas

        canvas = Canvas(
            id="https://example.org/canvas/empty",
            type="sc:Canvas",
            images=[]
        )
        issues = validate_canvas(canvas)

        assert len(issues) > 0
        assert any("images" in issue.path for issue in issues)


class TestValidationIssue:
    """Tests for ValidationIssue structure."""

    def test_validation_issue_has_path_and_message(self):
        """Test that validation issues include path and message."""
        data = load_json(str(FIXTURES_DIR / "manifest_invalid.json"))
        manifest = parse_manifest(data)
        issues = validate_manifest(manifest)

        assert len(issues) > 0
        issue = issues[0]
        assert hasattr(issue, "path")
        assert hasattr(issue, "message")
        assert isinstance(issue.path, str)
        assert isinstance(issue.message, str)
