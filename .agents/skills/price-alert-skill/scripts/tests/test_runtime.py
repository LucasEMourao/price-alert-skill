from __future__ import annotations

from pathlib import Path

import pytest

import price_alert_skill.config as config
from price_alert_skill.runtime import (
    detect_wsl,
    find_linux_browser_executable,
    resolve_runtime_environment,
)


def test_auto_detects_windows_runtime() -> None:
    runtime = resolve_runtime_environment(
        "auto",
        environ={},
        os_name="nt",
        proc_version="",
    )

    assert runtime.name == "windows"
    assert runtime.is_windows is True
    assert runtime.is_linux is False
    assert runtime.is_wsl is False


def test_auto_detects_linux_runtime() -> None:
    runtime = resolve_runtime_environment(
        "auto",
        environ={},
        os_name="posix",
        proc_version="Linux version generic",
    )

    assert runtime.name == "linux"
    assert runtime.is_linux is True
    assert runtime.is_wsl is False


def test_auto_detects_wsl_context() -> None:
    runtime = resolve_runtime_environment(
        "auto",
        environ={"WSL_DISTRO_NAME": "Ubuntu"},
        os_name="posix",
        proc_version="",
    )

    assert runtime.name == "linux"
    assert runtime.is_wsl is True
    assert runtime.wsl_distro == "Ubuntu"


def test_detect_wsl_from_proc_version() -> None:
    assert detect_wsl(environ={}, proc_version="microsoft-standard-WSL2") is True


def test_configured_runtime_overrides_host_detection() -> None:
    runtime = resolve_runtime_environment(
        "windows",
        environ={"WSL_DISTRO_NAME": "Ubuntu"},
        os_name="posix",
        proc_version="microsoft-standard-WSL2",
    )

    assert runtime.name == "windows"
    assert runtime.is_wsl is False


def test_invalid_runtime_raises() -> None:
    with pytest.raises(ValueError, match="PRICE_ALERT_RUNTIME"):
        resolve_runtime_environment("macos", environ={}, os_name="posix")


def test_find_linux_browser_executable_uses_first_available(monkeypatch) -> None:
    def fake_which(executable: str) -> str | None:
        if executable == "chromium":
            return "/usr/bin/chromium"
        return None

    monkeypatch.setattr("price_alert_skill.runtime.shutil.which", fake_which)

    assert find_linux_browser_executable() == "/usr/bin/chromium"


def test_config_chrome_path_override_wins(monkeypatch) -> None:
    monkeypatch.setattr(config, "WHATSAPP_CHROME_PATH", "/custom/chrome")

    assert config.resolve_whatsapp_chrome_path() == "/custom/chrome"


def test_config_linux_chrome_auto_detection(monkeypatch) -> None:
    monkeypatch.setattr(config, "WHATSAPP_CHROME_PATH", "")
    monkeypatch.setattr(config, "PRICE_ALERT_RUNTIME", "linux")
    monkeypatch.setattr(config, "find_linux_browser_executable", lambda: "/usr/bin/chromium")

    assert config.resolve_whatsapp_chrome_path() == "/usr/bin/chromium"


def test_config_profile_override_wins(monkeypatch) -> None:
    monkeypatch.setattr(config, "WHATSAPP_PROFILE_DIR", "/tmp/custom-profile")

    assert config.resolve_whatsapp_profile_dir() == "/tmp/custom-profile"


def test_config_uses_linux_profile_for_linux_runtime(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(config, "WHATSAPP_PROFILE_DIR", "")
    monkeypatch.setattr(config, "PRICE_ALERT_RUNTIME", "linux")
    monkeypatch.setattr(config, "resolve_skill_root", lambda: tmp_path)

    assert Path(config.resolve_whatsapp_profile_dir()).name == "linux_chrome_profile"


def test_config_reuses_existing_legacy_linux_profile(monkeypatch, tmp_path) -> None:
    legacy_profile = tmp_path / "data" / "whatsapp_session" / "chrome_profile"
    legacy_profile.mkdir(parents=True)
    monkeypatch.setattr(config, "WHATSAPP_PROFILE_DIR", "")
    monkeypatch.setattr(config, "PRICE_ALERT_RUNTIME", "linux")
    monkeypatch.setattr(config, "resolve_skill_root", lambda: tmp_path)

    assert Path(config.resolve_whatsapp_profile_dir()) == legacy_profile


def test_config_uses_local_app_data_profile_for_windows_runtime(monkeypatch) -> None:
    monkeypatch.setattr(config, "WHATSAPP_PROFILE_DIR", "")
    monkeypatch.setattr(config, "PRICE_ALERT_RUNTIME", "windows")
    monkeypatch.setenv("LOCALAPPDATA", "/tmp/local-app-data")

    profile_dir = Path(config.resolve_whatsapp_profile_dir())

    assert profile_dir == Path("/tmp/local-app-data") / "price-alert-skill" / "whatsapp_chrome_profile"
