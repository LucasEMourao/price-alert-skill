#!/usr/bin/env python3

"""Tests for send_to_whatsapp module.

These tests cover the utility functions and logic of the WhatsApp sender.
Browser automation (Playwright) is mocked to avoid requiring a real browser.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import price_alert_skill.config as config
from price_alert_skill import send_to_whatsapp
from price_alert_skill.send_to_whatsapp import (
    _download_image,
    _ensure_logged_in,
    _is_logged_in,
    _reset_whatsapp_session,
    _send_image_with_caption,
    _search_and_open_group,
    open_whatsapp_session,
)


class TestDownloadImage:
    """Tests for _download_image function."""

    @patch("price_alert_skill.send_to_whatsapp.requests.get")
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

    @patch("price_alert_skill.send_to_whatsapp.requests.get")
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

    @patch("price_alert_skill.send_to_whatsapp.requests.get")
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

    @patch("price_alert_skill.send_to_whatsapp.requests.get")
    def test_download_image_http_error(self, mock_get):
        import requests as req

        mock_get.side_effect = req.exceptions.HTTPError("404 Not Found")

        result = _download_image("https://example.com/missing.jpg")

        assert result is None

    @patch("price_alert_skill.send_to_whatsapp.requests.get")
    def test_download_image_timeout(self, mock_get):
        import requests as req

        mock_get.side_effect = req.exceptions.Timeout("Request timed out")

        result = _download_image("https://example.com/slow.jpg")

        assert result is None

    @patch("price_alert_skill.send_to_whatsapp.requests.get")
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
        page.url = "https://web.whatsapp.com/"

        def locator_side_effect(selector):
            locator = MagicMock()
            locator.first.is_visible.return_value = selector in ("#pane-side", "#side")
            return locator

        page.locator.side_effect = locator_side_effect

        assert _is_logged_in(page) is True

    def test_not_logged_in_qr_visible(self):
        page = MagicMock()
        page.url = "https://web.whatsapp.com/"

        def locator_side_effect(selector):
            locator = MagicMock()
            locator.first.is_visible.return_value = selector == 'canvas[aria-label*="Scan"]'
            return locator

        page.locator.side_effect = locator_side_effect

        assert _is_logged_in(page) is False


class TestEnsureLoggedIn:
    """Tests for _ensure_logged_in session waiting logic."""

    @patch("price_alert_skill.send_to_whatsapp.time.sleep", return_value=None)
    @patch("price_alert_skill.send_to_whatsapp._get_whatsapp_state")
    def test_non_headed_waits_for_existing_session(self, mock_state, _mock_sleep):
        page = MagicMock()
        page.url = "https://web.whatsapp.com/"
        page.wait_for_load_state.return_value = None
        mock_state.side_effect = ["loading", "loading", "logged_in"]

        _ensure_logged_in(page, headed=False, timeout_ms=10000)

    @patch("price_alert_skill.send_to_whatsapp.time.sleep", return_value=None)
    @patch("price_alert_skill.send_to_whatsapp._get_whatsapp_state")
    def test_non_headed_raises_when_session_is_gone(self, mock_state, _mock_sleep):
        page = MagicMock()
        page.url = "https://web.whatsapp.com/"
        page.wait_for_load_state.return_value = None
        mock_state.side_effect = ["loading", "logged_out"]

        with pytest.raises(RuntimeError, match="Not logged in"):
            _ensure_logged_in(page, headed=False, timeout_ms=10000)

    def test_logged_in_query_raises(self):
        page = MagicMock()
        page.url = "https://web.whatsapp.com/"
        page.locator.side_effect = Exception("selector error")

        assert _is_logged_in(page) is False


class TestOpenWhatsAppSession:
    """Tests for session bootstrap behavior."""

    @patch("playwright.sync_api.sync_playwright")
    @patch("price_alert_skill.send_to_whatsapp._search_and_open_group")
    @patch("price_alert_skill.send_to_whatsapp._find_group_search_box")
    @patch("price_alert_skill.send_to_whatsapp._ensure_logged_in")
    @patch("price_alert_skill.send_to_whatsapp._clear_stale_profile_lock_files")
    @patch("price_alert_skill.send_to_whatsapp.configure_utf8_stdio")
    def test_configures_utf8_stdio_before_launch(
        self,
        mock_configure_utf8_stdio,
        _mock_clear_locks,
        _mock_ensure_logged_in,
        _mock_find_group_search_box,
        _mock_search_and_open_group,
        mock_sync_playwright,
    ):
        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_playwright = MagicMock()
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context

        mock_sync_playwright.return_value.start.return_value = mock_playwright

        session = open_whatsapp_session(group_name="Grupo de Teste", headed=False)

        mock_configure_utf8_stdio.assert_called_once()
        assert session["page"] is mock_page
        assert session["context"] is mock_context
        assert session["playwright"] is mock_playwright

    @patch("playwright.sync_api.sync_playwright")
    @patch("price_alert_skill.send_to_whatsapp._search_and_open_group")
    @patch("price_alert_skill.send_to_whatsapp._find_group_search_box")
    @patch("price_alert_skill.send_to_whatsapp._ensure_logged_in")
    @patch("price_alert_skill.send_to_whatsapp._clear_stale_profile_lock_files")
    @patch("price_alert_skill.send_to_whatsapp.configure_utf8_stdio")
    def test_uses_resolved_profile_dir_at_launch_time(
        self,
        _mock_configure_utf8_stdio,
        _mock_clear_locks,
        _mock_ensure_logged_in,
        _mock_find_group_search_box,
        _mock_search_and_open_group,
        mock_sync_playwright,
        monkeypatch,
        tmp_path,
    ):
        profile_dir = tmp_path / "linux_chrome_profile"
        monkeypatch.setattr(
            send_to_whatsapp,
            "resolve_whatsapp_profile_dir",
            lambda: str(profile_dir),
        )

        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_playwright = MagicMock()
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_sync_playwright.return_value.start.return_value = mock_playwright

        open_whatsapp_session(group_name="Grupo de Teste", headed=False)

        launch_kwargs = mock_playwright.chromium.launch_persistent_context.call_args.kwargs
        assert launch_kwargs["user_data_dir"] == str(profile_dir)
        assert profile_dir.exists()

    def test_reset_session_removes_only_resolved_profile(self, tmp_path):
        active_profile = tmp_path / "linux_chrome_profile"
        other_profile = tmp_path / "windows_chrome_profile"
        active_profile.mkdir()
        other_profile.mkdir()
        (active_profile / "SingletonLock").write_text("lock", encoding="utf-8")
        (other_profile / "SingletonLock").write_text("lock", encoding="utf-8")

        _reset_whatsapp_session(str(active_profile))

        assert not active_profile.exists()
        assert other_profile.exists()

    @patch("playwright.sync_api.sync_playwright")
    @patch("price_alert_skill.send_to_whatsapp._search_and_open_group")
    @patch("price_alert_skill.send_to_whatsapp._find_group_search_box")
    @patch("price_alert_skill.send_to_whatsapp._ensure_logged_in")
    @patch("price_alert_skill.send_to_whatsapp._clear_stale_profile_lock_files")
    @patch("price_alert_skill.send_to_whatsapp.configure_utf8_stdio")
    def test_closes_playwright_when_session_open_fails(
        self,
        _mock_configure_utf8_stdio,
        _mock_clear_locks,
        mock_ensure_logged_in,
        _mock_find_group_search_box,
        _mock_search_and_open_group,
        mock_sync_playwright,
        monkeypatch,
        tmp_path,
    ):
        profile_dir = tmp_path / "linux_chrome_profile"
        monkeypatch.setattr(
            send_to_whatsapp,
            "resolve_whatsapp_profile_dir",
            lambda: str(profile_dir),
        )

        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_playwright = MagicMock()
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_sync_playwright.return_value.start.return_value = mock_playwright
        mock_ensure_logged_in.side_effect = RuntimeError("auth failed")

        with pytest.raises(RuntimeError, match="auth failed"):
            open_whatsapp_session(group_name="Grupo de Teste", headed=False)

        mock_context.close.assert_called_once()
        mock_playwright.stop.assert_called_once()


class TestSearchAndOpenGroup:
    """Tests for _search_and_open_group function."""

    @patch("price_alert_skill.send_to_whatsapp._wait_for_group_chat_open", return_value=True)
    def test_group_found(self, _mock_chat_open):
        page = MagicMock()
        search_box = MagicMock()
        page.wait_for_selector.return_value = search_box

        group_item = MagicMock()
        group_item.get_attribute.return_value = "Grupo de Ofertas"
        page.query_selector_all.return_value = [group_item]

        _search_and_open_group(page, "Grupo de Ofertas")

        search_box.click.assert_called()
        search_box.fill.assert_called_with("Grupo de Ofertas")
        assert group_item.evaluate.called or group_item.click.called

    @patch("price_alert_skill.send_to_whatsapp._wait_for_group_chat_open", return_value=False)
    def test_group_not_found(self, _mock_chat_open):
        page = MagicMock()
        search_box = MagicMock()
        page.wait_for_selector.return_value = search_box

        group_item = MagicMock()
        group_item.get_attribute.return_value = "Outro Grupo"
        group_item.text_content.return_value = "Outro Grupo"
        page.query_selector_all.return_value = [group_item]

        with pytest.raises(RuntimeError, match="not found"):
            _search_and_open_group(page, "Grupo de Ofertas")


class TestSendImageWithCaption:
    """Tests for _send_image_with_caption function."""

    def test_send_success(self):
        page = MagicMock()
        composer_ready = MagicMock()
        attach_btn = MagicMock()
        media_btn = MagicMock()
        caption_el = MagicMock()
        send_btn = MagicMock()

        def wait_for_selector_side_effect(selector, timeout=None):
            if selector == 'footer div[contenteditable="true"][role="textbox"]':
                return composer_ready
            if selector == 'button[aria-label="Anexar"]':
                return attach_btn
            if selector == 'button[aria-label="Fotos e vídeos"]':
                return media_btn
            if selector in (
                'div[contenteditable="true"][data-lexical-editor="true"]',
                'div[contenteditable="true"][role="textbox"]',
                'div[contenteditable="true"]',
            ):
                return caption_el
            if selector in (
                'button[aria-label="Enviar"]',
                'button[aria-label="Send"]',
                'button[title="Send"]',
                'button[data-testid="compose-btn-send"]',
                'span[data-icon="send"]',
            ):
                return send_btn
            raise AssertionError(f"Unexpected selector: {selector}")

        page.wait_for_selector.side_effect = wait_for_selector_side_effect

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
        page.click.assert_any_call('button[aria-label="Anexar"]')
        page.click.assert_any_call('button[aria-label="Fotos e vídeos"]')
        caption_el.fill.assert_called_with("Test caption")
        send_btn.click.assert_called()

    def test_send_success_with_direct_file_input_fallback(self):
        page = MagicMock()
        file_input = MagicMock()
        caption_el = MagicMock()
        send_btn = MagicMock()

        def wait_for_selector_side_effect(selector, timeout=None):
            if selector == 'footer div[contenteditable="true"][role="textbox"]':
                return MagicMock()
            if selector == 'button[aria-label="Anexar"]':
                return MagicMock()
            if selector == 'input[type="file"][accept*="image"]':
                return file_input
            if selector in (
                'div[contenteditable="true"][data-lexical-editor="true"]',
                'div[contenteditable="true"][role="textbox"]',
                'div[contenteditable="true"]',
            ):
                return caption_el
            if selector in (
                'button[aria-label="Enviar"]',
                'button[aria-label="Send"]',
                'button[title="Send"]',
                'button[data-testid="compose-btn-send"]',
                'span[data-icon="send"]',
            ):
                return send_btn
            raise Exception("not found")

        page.wait_for_selector.side_effect = wait_for_selector_side_effect

        result = _send_image_with_caption(
            page, "/tmp/test.jpg", "Test caption", delay_between=0.1
        )

        assert result is True
        file_input.set_input_files.assert_called_with("/tmp/test.jpg")

    def test_send_failure_returns_false(self):
        page = MagicMock()
        page.wait_for_selector.side_effect = Exception("timeout")

        result = _send_image_with_caption(page, "/tmp/test.jpg", "Test caption")

        assert result is False


class TestSendDealsIntegration:
    """Integration-style tests for send_deals_to_whatsapp (mocked browser)."""

    @patch("playwright.sync_api.sync_playwright")
    def test_send_deals_all_succeed(self, mock_playwright):
        from price_alert_skill.send_to_whatsapp import send_deals_to_whatsapp

        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_p = MagicMock()
        mock_p.chromium.launch_persistent_context.return_value = mock_context
        mock_playwright.return_value.__enter__ = MagicMock(return_value=mock_p)
        mock_playwright.return_value.__exit__ = MagicMock(return_value=False)

        deals = [
            {
                "title": "Mouse Gamer",
                "url": "https://example.com/1",
                "dedup_key": "deal-1",
                "image_url": "https://example.com/mouse.jpg",
                "message": "Test message 1",
            }
        ]

        with patch("price_alert_skill.send_to_whatsapp._download_image") as mock_dl, \
             patch("price_alert_skill.send_to_whatsapp._send_image_with_caption", return_value=True), \
             patch("price_alert_skill.send_to_whatsapp._search_and_open_group"), \
             patch("price_alert_skill.send_to_whatsapp._ensure_logged_in"):
            mock_dl.return_value = "/tmp/test.jpg"

            results = send_deals_to_whatsapp(
                deals=deals,
                group_name="Test Group",
                headed=False,
            )

        assert results["sent"] == 1
        assert results["failed"] == 0
        assert results["successful_keys"] == ["deal-1"]

    @patch("playwright.sync_api.sync_playwright")
    def test_send_deals_no_image_url(self, mock_playwright):
        from price_alert_skill.send_to_whatsapp import send_deals_to_whatsapp

        mock_page = MagicMock()
        mock_context = MagicMock()
        mock_context.new_page.return_value = mock_page

        mock_p = MagicMock()
        mock_p.chromium.launch_persistent_context.return_value = mock_context
        mock_playwright.return_value.__enter__ = MagicMock(return_value=mock_p)
        mock_playwright.return_value.__exit__ = MagicMock(return_value=False)

        deals = [
            {
                "title": "Product No Image",
                "url": "https://example.com/1",
                "dedup_key": "deal-1",
                "image_url": None,
                "message": "Test message",
            }
        ]

        with patch("price_alert_skill.send_to_whatsapp._search_and_open_group"), \
             patch("price_alert_skill.send_to_whatsapp._ensure_logged_in"):
            results = send_deals_to_whatsapp(
                deals=deals,
                group_name="Test Group",
                headed=False,
            )

        assert results["sent"] == 0
        assert results["failed"] == 1
        assert results["errors"][0]["reason"] == "no image_url"
        assert results["errors"][0]["url"] == "https://example.com/1"


class TestCliGroupResolution:
    """Tests for CLI fallback to WHATSAPP_GROUP from .env."""

    @patch("price_alert_skill.send_to_whatsapp.send_deals_to_whatsapp", return_value={"sent": 1, "failed": 0, "errors": []})
    def test_main_uses_env_group_when_group_flag_is_missing(self, mock_send, monkeypatch, tmp_path):
        deals_path = tmp_path / "deals.json"
        deals_path.write_text(json.dumps({
            "messages": [{
                "title": "Mouse Gamer",
                "url": "https://example.com/1",
                "image_url": "https://example.com/mouse.jpg",
                "message": "Test message",
            }]
        }))

        monkeypatch.setattr(config, "WHATSAPP_GROUP", "Grupo via Env")
        monkeypatch.setattr(sys, "argv", ["send_to_whatsapp.py", "--deals", str(deals_path)])

        send_to_whatsapp.main()

        assert mock_send.call_args.kwargs["group_name"] == "Grupo via Env"

    @patch("price_alert_skill.send_to_whatsapp.send_deals_to_whatsapp", return_value={"sent": 1, "failed": 0, "errors": []})
    def test_main_prefers_cli_group_over_env(self, mock_send, monkeypatch, tmp_path):
        deals_path = tmp_path / "deals.json"
        deals_path.write_text(json.dumps({
            "messages": [{
                "title": "Mouse Gamer",
                "url": "https://example.com/1",
                "image_url": "https://example.com/mouse.jpg",
                "message": "Test message",
            }]
        }))

        monkeypatch.setattr(config, "WHATSAPP_GROUP", "Grupo via Env")
        monkeypatch.setattr(
            sys,
            "argv",
            ["send_to_whatsapp.py", "--deals", str(deals_path), "--group", "Grupo via CLI"],
        )

        send_to_whatsapp.main()

        assert mock_send.call_args.kwargs["group_name"] == "Grupo via CLI"
