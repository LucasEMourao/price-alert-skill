from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import pytest
import requests

from price_alert_skill.core.adapters.baileys_sender import BaileysDealChatSenderAdapter


VISUAL_DEALS = [
    {
        "title": "Wella Invigo Fusion Shampoo 1L",
        "url": "https://www.amazon.com.br/dp/B06Y1YBBMV?tag=brunoentende-20",
        "dedup_key": "www.amazon.com.br/dp/b06y1ybbmv|169.90",
        "image_url": "https://m.media-amazon.com/images/I/41I-Vcc1qML._AC_UL320_.jpg",
        "message": (
            "OFERTA DO DIA\n\nWella Invigo Fusion Shampoo 1L\n\n"
            "35% OFF\nAntes: R$ 261,36\nHoje: R$ 169,90"
        ),
    },
    {
        "title": "Base Matte Hidraluronic N005, Vult, N005",
        "url": "https://www.amazon.com.br/dp/B098Y8CHGW?tag=brunoentende-20",
        "dedup_key": "amazon_br|beleza_maquiagem|base matte hidraluronic vult|20.61",
        "image_url": "https://m.media-amazon.com/images/I/61Y38LzCrIL._AC_UL320_.jpg",
        "message": (
            "OFERTA DO DIA\n\nBase Matte Hidraluronic N005, Vult, N005\n\n"
            "51% OFF\nAntes: R$ 41,90\nHoje: R$ 20,61"
        ),
    },
    {
        "title": "Hidramais Masc Facial Carvao Ativado Detox 8g",
        "url": "https://www.amazon.com.br/dp/B0BXQZ2Y3F?tag=brunoentende-20",
        "dedup_key": "www.amazon.com.br/dp/b0bxqz2y3f|3.02",
        "image_url": "https://m.media-amazon.com/images/I/61XQgfXotzL._AC_UL320_.jpg",
        "message": (
            "OFERTA DO DIA\n\nHidramais Masc Facial Carvao Ativado Detox 8g\n\n"
            "38% OFF\nAntes: R$ 4,90\nHoje: R$ 3,02"
        ),
    },
]


class DiskImageStub:
    """Baileys-like stub that writes the image payload to disk instead of WhatsApp."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.calls: list[dict[str, Any]] = []

    def send_image(self, *, image_url: str, caption: str) -> dict[str, Any]:
        index = len(self.calls) + 1
        source_path = self._write_image(index, image_url)
        self.calls.append(
            {
                "index": index,
                "image_url": image_url,
                "output_path": str(source_path),
                "caption": caption,
            }
        )
        return {
            "success": True,
            "message_id": f"stub-{index}",
            "jid": "stub@g.us",
        }

    def _write_image(self, index: int, image_url: str) -> Path:
        title = VISUAL_DEALS[index - 1]["title"]
        destination = self.output_dir / f"{index:02d}-{_slugify(title)}.jpg"
        source_path = Path(image_url)
        if source_path.exists():
            shutil.copyfile(source_path, destination)
            return destination

        response = requests.get(image_url, stream=True, timeout=30)
        response.raise_for_status()
        with destination.open("wb") as image_file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    image_file.write(chunk)
        return destination


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower())
    return normalized.strip("-")


@pytest.mark.skipif(
    os.environ.get("PRICE_ALERT_WRITE_IMAGE_STUBS") != "1",
    reason="Set PRICE_ALERT_WRITE_IMAGE_STUBS=1 to write visual image fixtures.",
)
def test_baileys_image_stub_writes_normalized_product_images() -> None:
    output_dir = Path(".pytest-tmp") / "whatsapp-image-stub"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter = BaileysDealChatSenderAdapter()
    stub = DiskImageStub(output_dir)
    manifest: list[dict[str, Any]] = []

    for deal in VISUAL_DEALS:
        result = adapter(stub, deal, delay_between=0, max_retries=0)
        assert result["success"] is True
        manifest.append(
            {
                "title": deal["title"],
                "source_image_url": deal["image_url"],
                "output_path": stub.calls[-1]["output_path"],
                "caption": stub.calls[-1]["caption"],
            }
        )

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps({"images": manifest}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    assert len(list(output_dir.glob("*.jpg"))) == len(VISUAL_DEALS)
    assert manifest_path.exists()
