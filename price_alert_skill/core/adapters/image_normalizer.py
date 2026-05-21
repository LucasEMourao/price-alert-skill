"""Image normalization helpers for WhatsApp media delivery."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import requests


DEFAULT_CANVAS_SIZE = 800
DEFAULT_JPEG_QUALITY = 92
IMAGE_DOWNLOAD_TIMEOUT_SECONDS = 30
_AMAZON_IMAGE_MODIFIER_RE = re.compile(r"\._[^/]*_\.")
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


class ImageNormalizationError(RuntimeError):
    """Raised when an image cannot be prepared for WhatsApp delivery."""


class ImageMagickNotFoundError(ImageNormalizationError):
    """Raised when no ImageMagick executable is available."""


def resolve_imagemagick_binary() -> str:
    """Return a usable ImageMagick executable path."""
    configured = os.environ.get("PRICE_ALERT_IMAGEMAGICK_BIN", "").strip()
    candidates = [configured] if configured else []
    candidates.extend(
        candidate
        for candidate in (shutil.which("magick"), shutil.which("convert"))
        if candidate
    )

    for candidate in candidates:
        if _is_imagemagick_binary(candidate):
            return candidate

    raise ImageMagickNotFoundError(
        "ImageMagick was not found. Install imagemagick or set "
        "PRICE_ALERT_IMAGEMAGICK_BIN."
    )


def _is_imagemagick_binary(candidate: str) -> bool:
    try:
        result = subprocess.run(
            [candidate, "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    return result.returncode == 0 and "imagemagick" in (
        f"{result.stdout}\n{result.stderr}".lower()
    )


def preferred_image_urls(image_url: str) -> list[str]:
    """Return best-effort source URLs, trying higher-quality Amazon images first."""
    parsed = urlparse(image_url)
    if parsed.scheme not in {"http", "https"}:
        return [image_url]

    candidates: list[str] = []
    if "media-amazon." in parsed.netloc:
        upgraded = _AMAZON_IMAGE_MODIFIER_RE.sub(".", image_url)
        if upgraded != image_url:
            candidates.append(upgraded)

    candidates.append(image_url)
    return list(dict.fromkeys(candidates))


def normalize_image_to_path(
    source_image: str | Path,
    output_path: str | Path,
    *,
    canvas_size: int = DEFAULT_CANVAS_SIZE,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    imagemagick_bin: str | None = None,
) -> Path:
    """Normalize an image into a square JPEG without stretching or cropping."""
    source_path = Path(source_image)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    binary = imagemagick_bin or resolve_imagemagick_binary()
    geometry = f"{int(canvas_size)}x{int(canvas_size)}"

    command = [
        binary,
        str(source_path),
        "-auto-orient",
        "-colorspace",
        "sRGB",
        "-resize",
        geometry,
        "-background",
        "white",
        "-gravity",
        "center",
        "-extent",
        geometry,
        "-alpha",
        "remove",
        "-alpha",
        "off",
        "-strip",
        "-quality",
        str(int(jpeg_quality)),
        str(destination),
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        error_output = (result.stderr or result.stdout or "").strip()
        raise ImageNormalizationError(
            f"ImageMagick failed to normalize image: {error_output}"
        )

    return destination


@contextmanager
def prepare_whatsapp_image(
    image_url: str,
    *,
    canvas_size: int = DEFAULT_CANVAS_SIZE,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
) -> Iterator[str]:
    """Download and normalize a WhatsApp image, yielding a temporary local path."""
    with tempfile.TemporaryDirectory(prefix="price_alert_whatsapp_image_") as temp_dir:
        temp_path = Path(temp_dir)
        parsed = urlparse(image_url)
        if parsed.scheme in {"http", "https"}:
            errors: list[str] = []
            for index, candidate_url in enumerate(preferred_image_urls(image_url), start=1):
                try:
                    source_path = _download_image(candidate_url, temp_path / f"source_{index}")
                    output_path = temp_path / f"whatsapp_image_{index}.jpg"
                    normalize_image_to_path(
                        source_path,
                        output_path,
                        canvas_size=canvas_size,
                        jpeg_quality=jpeg_quality,
                    )
                    yield str(output_path)
                    return
                except Exception as exc:
                    errors.append(f"{candidate_url}: {exc}")

            raise ImageNormalizationError(
                "Failed to prepare image for WhatsApp. " + " | ".join(errors)
            )

        source_path = _materialize_local_image(image_url)
        output_path = temp_path / "whatsapp_image.jpg"
        normalize_image_to_path(
            source_path,
            output_path,
            canvas_size=canvas_size,
            jpeg_quality=jpeg_quality,
        )
        yield str(output_path)


def _materialize_local_image(image_url: str) -> Path:
    local_path = Path(image_url)
    if not local_path.exists():
        raise ImageNormalizationError(f"Local image does not exist: {image_url}")
    return local_path


def _download_image(image_url: str, destination_base: Path) -> Path:
    response = requests.get(
        image_url,
        headers=_REQUEST_HEADERS,
        timeout=IMAGE_DOWNLOAD_TIMEOUT_SECONDS,
        stream=True,
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type")
    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_type and not normalized_type.startswith("image/"):
        raise ImageNormalizationError(f"Unexpected image content type: {content_type}")

    suffix = _resolve_image_suffix(image_url, content_type)
    destination = destination_base.with_suffix(suffix)
    with destination.open("wb") as image_file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                image_file.write(chunk)

    if destination.stat().st_size == 0:
        raise ImageNormalizationError("Downloaded image is empty")
    return destination


def _resolve_image_suffix(image_url: str, content_type: str | None) -> str:
    path_suffix = Path(urlparse(image_url).path).suffix.lower()
    if path_suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return path_suffix

    normalized_type = (content_type or "").split(";", 1)[0].strip().lower()
    return {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(normalized_type, ".jpg")
