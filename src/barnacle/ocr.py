from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import typer

# CATMuS Print Fondue Large model - default for Kraken OCR
DEFAULT_MODEL = "10.5281/zenodo.10592716"


class OCRBackend(Protocol):
    """Minimal interface for an OCR backend."""

    name: str

    def resolve_model(self, model_ref: str) -> str:
        ...

    def ocr_image(self, image_path: Path, *, model: str) -> str:
        ...


@dataclass
class KrakenBackend:
    """Kraken-backed OCR implementation using the kraken CLI.

    Uses the pipeline:
        kraken -i <input> <output> binarize segment -bl ocr -m <model>

    The `-bl` flag enables baseline segmentation, which matches baseline-trained
    recognizers and avoids the warning about baseline recognizers being applied
    to bbox segmentation.
    """

    name: str = "kraken"
    model_auto_install: bool = True
    logger: logging.Logger | None = None

    def resolve_model(self, model_ref: str) -> str:
        """Resolve a model reference.

        If `model_ref` looks like a DOI and auto-install is enabled, runs `kraken get`.
        Otherwise returns `model_ref` unchanged.
        """
        looks_like_doi = model_ref.startswith("10.") or "zenodo." in model_ref
        if not (looks_like_doi and self.model_auto_install):
            return model_ref

        try:
            proc = subprocess.run(
                ["kraken", "get", model_ref],
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError as e:
            raise typer.BadParameter(
                "Kraken CLI not found. Install `kraken` and ensure `kraken` is on your PATH."
            ) from e
        except subprocess.CalledProcessError as e:
            raise typer.BadParameter(f"`kraken get` failed:\n{e.stderr or e.stdout}") from e

        out = (proc.stdout or "") + "\n" + (proc.stderr or "")
        # Best-effort parse: "(model files: foo.mlmodel)"
        m = re.search(r"\(model files:\s*([^\)]+)\)", out)
        if m:
            first = m.group(1).strip().split()[0].strip(",")
            return first

        return model_ref

    def ocr_image(self, image_path: Path, *, model: str) -> str:
        """Run OCR on a single image and return recognized text (possibly empty)."""
        with tempfile.TemporaryDirectory(prefix="barnacle-kraken-") as td:
            out_path = Path(td) / "out.txt"
            try:
                subprocess.run(
                    [
                        "kraken",
                        "-i",
                        str(image_path),
                        str(out_path),
                        "binarize",
                        "segment",
                        "-bl",
                        "ocr",
                        "-m",
                        model,
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except FileNotFoundError as e:
                raise typer.BadParameter(
                    "Kraken CLI not found. Install `kraken` and ensure `kraken` is on your PATH."
                ) from e
            except subprocess.CalledProcessError as e:
                raise typer.BadParameter(f"Kraken OCR failed:\n{e.stderr or e.stdout}") from e

            if out_path.exists():
                return out_path.read_text(encoding="utf-8", errors="replace")

            if self.logger:
                self.logger.info(
                    "kraken_no_output",
                    extra={"image_path": str(image_path), "model": model},
                )
            return ""
