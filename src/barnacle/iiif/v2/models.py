"""
Pydantic models for IIIF Presentation API 2.1.

These models provide type-safe representations of IIIF resources with
traversal helpers and validation. They implement the subset of IIIF 2.1
needed for Barnacle's OCR pipeline.
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, ConfigDict


class ImageService(BaseModel):
    """
    IIIF Image API service descriptor.

    Provides methods to construct IIIF Image API URLs for requesting images
    with specific parameters (size, format, quality, etc.).
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(alias="@id")
    type: str | None = Field(default=None, alias="@type")
    profile: str | list[Any] | None = None
    context: str | list[Any] | None = Field(default=None, alias="@context")

    def image_url(
        self,
        *,
        region: str = "full",
        size: str = "!3000,3000",
        rotation: str = "0",
        quality: str = "default",
        fmt: str = "jpg",
    ) -> str:
        """
        Generate IIIF Image API URL.

        Parameters:
            region: IIIF region parameter (default: "full")
            size: IIIF size parameter (default: "!3000,3000")
            rotation: IIIF rotation parameter (default: "0")
            quality: IIIF quality parameter (default: "default")
            fmt: Image format (default: "jpg")

        Returns:
            Full IIIF Image API URL

        Example:
            >>> service = ImageService(id="https://iiif.example.org/image1")
            >>> service.image_url(size="200,200", fmt="png")
            'https://iiif.example.org/image1/full/200,200/0/default.png'
        """
        base = self.id.rstrip("/")
        return f"{base}/{region}/{size}/{rotation}/{quality}.{fmt}"


class ImageResource(BaseModel):
    """
    Image resource in an annotation.

    Represents the image content linked to a canvas via an annotation.
    May have one or more IIIF Image API services.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = Field(default=None, alias="@id")
    type: str | None = Field(default=None, alias="@type")
    format: str | None = None
    width: int | None = None
    height: int | None = None
    service: ImageService | list[ImageService] | None = None

    def first_service(self) -> ImageService | None:
        """
        Get first image service.

        Convenience method for canvases with single image service (common case).

        Returns:
            First ImageService if available, None otherwise
        """
        if self.service is None:
            return None
        if isinstance(self.service, ImageService):
            return self.service
        if isinstance(self.service, list) and len(self.service) > 0:
            return self.service[0]
        return None


class Annotation(BaseModel):
    """
    IIIF annotation (typically linking canvas to image).

    In IIIF Presentation 2.1, annotations connect canvases to their
    image content resources.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = Field(default=None, alias="@id")
    type: str | None = Field(default=None, alias="@type")
    motivation: str | None = None
    resource: ImageResource
    on: str | None = None


class Canvas(BaseModel):
    """
    IIIF canvas (represents a page/view).

    A canvas is the virtual container for page content. It has dimensions
    and links to one or more images via annotations.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(alias="@id")
    type: str = Field(alias="@type")
    label: str | dict | list | None = None
    width: int | None = None
    height: int | None = None
    images: list[Annotation] = Field(default_factory=list)

    def primary_image_service(self) -> ImageService | None:
        """
        Get primary image service for OCR.

        Returns the first available image service from the canvas's
        primary image annotation.

        Returns:
            Primary ImageService if available, None otherwise
        """
        if not self.images:
            return None
        first_anno = self.images[0]
        return first_anno.resource.first_service()

    def image_url(
        self,
        *,
        region: str = "full",
        size: str = "!3000,3000",
        rotation: str = "0",
        quality: str = "default",
        fmt: str = "jpg",
    ) -> str | None:
        """
        Generate IIIF Image API URL for primary image.

        Convenience method that gets the primary image service and
        generates its IIIF URL with specified parameters.

        Parameters:
            region: IIIF region parameter
            size: IIIF size parameter
            rotation: IIIF rotation parameter
            quality: IIIF quality parameter
            fmt: Image format

        Returns:
            IIIF Image API URL if service available, None otherwise

        Example:
            >>> url = canvas.image_url(size="!2000,2000", fmt="jpg")
        """
        service = self.primary_image_service()
        if service is None:
            return None
        return service.image_url(
            region=region, size=size, rotation=rotation, quality=quality, fmt=fmt
        )


class Sequence(BaseModel):
    """
    IIIF sequence (ordered list of canvases).

    A manifest contains one or more sequences. Each sequence defines
    a reading order for its canvases.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = Field(default=None, alias="@id")
    type: str = Field(alias="@type")
    canvases: list[Canvas] = Field(default_factory=list)


class Manifest(BaseModel):
    """
    IIIF Presentation 2.1 Manifest.

    A manifest represents a single object (typically a book, manuscript,
    or other compound object). It contains sequences of canvases that
    define the viewing/reading order.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(alias="@id")
    type: Literal["sc:Manifest"] = Field(alias="@type")
    label: str | dict | list | None = None
    metadata: list[dict[str, Any]] | None = None
    sequences: list[Sequence] = Field(default_factory=list)

    def canvases(self) -> list[Canvas]:
        """
        Get all canvases in reading order.

        Traverses all sequences and returns all canvases in order.
        This is the primary method for iterating pages in a manifest.

        Returns:
            List of canvases in reading order

        Example:
            >>> manifest = load_manifest(url)
            >>> for canvas in manifest.canvases():
            ...     print(canvas.id)
        """
        result: list[Canvas] = []
        for seq in self.sequences:
            result.extend(seq.canvases)
        return result


class Collection(BaseModel):
    """
    IIIF Presentation 2.1 Collection.

    A collection is a grouping of manifests and/or other collections.
    It provides a hierarchical organization of IIIF resources.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str = Field(alias="@id")
    type: Literal["sc:Collection"] = Field(alias="@type")
    label: str | dict | list | None = None
    manifests: list[dict[str, Any]] = Field(default_factory=list)
    collections: list[dict[str, Any]] = Field(default_factory=list)

    def manifest_ids(self) -> list[str]:
        """
        Extract manifest @id values.

        Convenience method to get all manifest URLs from the collection
        without needing to fetch the full manifest JSON.

        Returns:
            List of manifest URLs

        Example:
            >>> collection = load_collection(url)
            >>> for manifest_id in collection.manifest_ids():
            ...     print(manifest_id)
        """
        return [m.get("@id") for m in self.manifests if "@id" in m]
