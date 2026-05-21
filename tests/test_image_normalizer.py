from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from price_alert_skill.core.adapters.image_normalizer import (
    preferred_image_urls,
    normalize_image_to_path,
    resolve_imagemagick_binary,
)


def _imagemagick_bin() -> str:
    try:
        return resolve_imagemagick_binary()
    except Exception as exc:
        pytest.skip(f"ImageMagick is not available: {exc}")


def _create_image(path: Path, size: tuple[int, int], color: str, binary: str) -> None:
    subprocess.run(
        [binary, "-size", f"{size[0]}x{size[1]}", f"xc:{color}", str(path)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _identify_size(path: Path, binary: str) -> tuple[int, int]:
    binary_name = Path(binary).name.lower()
    command = (
        [binary, "identify", "-format", "%w %h", str(path)]
        if binary_name.startswith("magick")
        else ["identify", "-format", "%w %h", str(path)]
    )
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    width, height = result.stdout.strip().split()
    return int(width), int(height)


def test_preferred_image_urls_upgrades_amazon_thumbnail_url() -> None:
    image_url = "https://m.media-amazon.com/images/I/41I-Vcc1qML._AC_UL320_.jpg"

    assert preferred_image_urls(image_url) == [
        "https://m.media-amazon.com/images/I/41I-Vcc1qML.jpg",
        image_url,
    ]


@pytest.mark.parametrize(
    ("source_size", "color"),
    [
        ((240, 900), "red"),
        ((900, 240), "blue"),
        ((640, 640), "green"),
    ],
)
def test_normalize_image_to_path_outputs_square_jpeg(
    tmp_path: Path,
    source_size: tuple[int, int],
    color: str,
) -> None:
    binary = _imagemagick_bin()
    source_path = tmp_path / "source.png"
    output_path = tmp_path / "normalized.jpg"
    _create_image(source_path, source_size, color, binary)

    normalize_image_to_path(source_path, output_path, imagemagick_bin=binary)

    assert output_path.exists()
    assert _identify_size(output_path, binary) == (800, 800)
