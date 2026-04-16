#!/usr/bin/env python3

"""Tests for send_to_whatsapp module.

These tests cover the utility functions and logic of the WhatsApp sender.
Browser automation (Playwright) is mocked to avoid requiring a real browser.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from send_to_whatsapp import (
    _download_image,
    _is_logged_in,
    _send_image_with_caption,
    _search_and_open_group,
)


class TestDownloadImage:
    """Tests for _download_image function."""

    @patch("send_to_whatsapp.requests.get")
    def test_download_image_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b"fake", b"image", b"data"]
        mock_get.return_value = mock_response

        url = "https://example.com/image.jpg"
        result = _download_image(url)

        assert result is not None
        assert result.endswith(".jpg")
        assert Path(result).exists()
        Path(result).unlink()

    @patch("send_to_whatsapp.requests.get")
    def test_download_image_png(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b"png", b"data"]
        mock_get.return_value = mock_response

        url = "https://example.com/product.png"
        result = _download_image(url)

        assert result is not None
        assert result.endswith(".png")
        Path(result).unlink()

    @patch("send_to_whatsapp.requests.get")
    def test_download_image_no_extension_defaults_to_jpg(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b"data"]
        mock_get.return_value = mock_response

        url = "https://example.com/image"
        result = _download_image(url)

        assert result is not None
        assert result.endswith(".jpg")
        Path(result).unlink()

    @patch("send_to_whatsapp.requests.get")
    def test_download_image_http_error(self, mock_get):
        import requests as req

        mock_get.side_effect = req.exceptions.HTTPError("404 Not Found")

        result = _download_image("https://example.com/missing.jpg")

        assert result is None

    @patch("send_to_whatsapp.requests.get")
    def test_download_image_timeout(self, mock_get):
        import requests as req

        mock_get.side_effect = req.exceptions.Timeout("Request timed out")

        result = _download_image("https://example.com/slow.jpg")

        assert result is None

    @patch("send_to_whatsapp.requests.get")
    def test_download_image_webp(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [b"webp"]
        mock_get.return_value = mock_response

        url = "https://example.com/photo.webp"
        result = _download_image(url)

        assert result is not None
        assert result.endswith(".webp")
        Path(result).unlink()


class TestIsLoggedIn:
    """Tests for _is_logged_in function."""

    def test_logged_in_no_qr(self):
        page = MagicMock()
        page.query_selector.return_value = None

        assert _is_logged_in(page) is True

    def test_not_logged_in_qr_visible(self):
        page = MagicMock()
        page.query_selector.return_value = MagicMock()

        assert _is_logged_in(page) is False

    def test_logged_in_query_raises(self):
        page = MagicMock()
        page.query_selector.side_effect = Exception("selector error")

        assert _is_logged_in(page) is True


class TestSearchAndOpenGroup:
    """Tests for _search_and_open_group function."""

    def test_group_found(self):
        page = MagicMock()
        search_box = MagicMock()
        page.wait_for_selector.return_value = search_box

        group_item = MagicMock()
        group_item.get_attribute.return_value = "Grupo de Ofertas"
        page.query_selector_all.return_value = [group_item]

        _search_and_open_group(page, "Grupo de Ofertas")

        search_box.click.assert_called()
        search_box.fill.assert_called_with("Grupo de Ofertas")
        group_item.click.assert_called()

    def test_group_not_found(self):
        page = MagicMock()
        search_box = MagicMock()
        page.wait_for_selector.return_value = search_box

        group_item = MagicMock()
        group_item.get_attribute.return_value = "Outro Grupo"
        page.query_selector_all.return_value = [group_item]

        with pytest.raises(RuntimeError, match="not found"):
            _search_and_open_group(page, "Grupo de Ofertas")


class TestSendImageWithCaption:
    """Tests for _send_image_with_caption function."""

    def test_send_success(self):
        page = MagicMock()
        page.wait_for_selector.return_value = True

        mock_fc_info = MagicMock()
        mock_file_chooser = MagicMock()
        mock_fc_info.value = mock_file_chooser
        page.expect_file_chooser.return_value.__enter__ = MagicMock(
            return_value=mock_fc_info
        )
        page.expect_file_chooser.return_value.__exit__ = MagicMock(
            return_value=False
        )

        result = _send_image_with_caption(
            page, "/tmp/test.jpg", "Test caption", delay_between=0.1
        )

        assert result is True
        page.click.assert_any_call('div[title="Attach"]')
        page.keyboard.type.assert_called()

    def test_send_failure_returns_false(self):
        page = MagicMock()
        page.wait_for_selector.side_effect = Exception("timeout")

        result = _send_image_with_caption(page, "/tmp/test.jpg", "Test caption")

        assert result is False


class TestSendDealsIntegration:
    """Integration-style tests for send_deals_to_whatsapp (mocked browser)."""

    @patch("playwright.sync_api.sync_playwright")
    def test_send_deals_all_succeed(self, mock_playwright):
        from send_to_whatsapp import send_deals_to_whatsapp

        mock_page = MagicMock()
        mock_page.query_selector.return_value = None
        mock_context = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__enter__ = MagicMock(return_value=mock_p)
        mock_playwright.return_value.__exit__ = MagicMock(return_value=False)

        deals = [
            {
                "title": "Mouse Gamer",
                "url": "https://example.com/1",
                "image_url": "https://example.com/mouse.jpg",
                "message": "Test message 1",
            }
        ]

        with patch("send_to_whatsapp._download_image") as mock_dl, \
             patch("send_to_whatsapp._send_image_with_caption", return_value=True), \
             patch("send_to_whatsapp._search_and_open_group"):
            mock_dl.return_value = "/tmp/test.jpg"

            results = send_deals_to_whatsapp(
                deals=deals,
                group_name="Test Group",
                headed=False,
            )

        assert results["sent"] == 1
        assert results["failed"] == 0

    @patch("playwright.sync_api.sync_playwright")
    def test_send_deals_no_image_url(self, mock_playwright):
        from send_to_whatsapp import send_deals_to_whatsapp

        mock_page = MagicMock()
        mock_page.query_selector.return_value = None
        mock_context = MagicMock()
        mock_browser = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        mock_p = MagicMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_playwright.return_value.__enter__ = MagicMock(return_value=mock_p)
        mock_playwright.return_value.__exit__ = MagicMock(return_value=False)

        deals = [
            {
                "title": "Product No Image",
                "url": "https://example.com/1",
                "image_url": None,
                "message": "Test message",
            }
        ]

        with patch("send_to_whatsapp._search_and_open_group"):
            results = send_deals_to_whatsapp(
                deals=deals,
                group_name="Test Group",
                headed=False,
            )

        assert results["sent"] == 0
        assert results["failed"] == 1
        assert results["errors"][0]["reason"] == "no image_url"
