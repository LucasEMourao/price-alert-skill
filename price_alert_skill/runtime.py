"""Runtime detection helpers for host-specific adapters."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class RuntimeEnvironment:
    """Resolved host runtime used to pick OS-specific adapters."""

    name: str
    is_wsl: bool = False
    wsl_distro: str = ""

    @property
    def is_windows(self) -> bool:
        return self.name == "windows"

    @property
    def is_linux(self) -> bool:
        return self.name == "linux"


def _read_proc_version(proc_version_path: Path = Path("/proc/version")) -> str:
    try:
        return proc_version_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def detect_wsl(
    *,
    environ: Mapping[str, str] | None = None,
    proc_version: str | None = None,
) -> bool:
    """Return True when the current Linux runtime is hosted by WSL."""
    env = environ if environ is not None else os.environ
    if env.get("WSL_DISTRO_NAME") or env.get("WSL_INTEROP"):
        return True

    version_text = proc_version if proc_version is not None else _read_proc_version()
    return "microsoft" in version_text.lower() or "wsl" in version_text.lower()


def resolve_runtime_environment(
    configured_runtime: str = "auto",
    *,
    environ: Mapping[str, str] | None = None,
    os_name: str | None = None,
    proc_version: str | None = None,
) -> RuntimeEnvironment:
    """Resolve the active runtime from env/config and host detection."""
    env = environ if environ is not None else os.environ
    runtime = (configured_runtime or "auto").strip().lower()
    host_os_name = os_name if os_name is not None else os.name
    wsl_distro = env.get("WSL_DISTRO_NAME", "")

    if runtime not in {"auto", "windows", "linux"}:
        raise ValueError(
            "PRICE_ALERT_RUNTIME must be one of: auto, windows, linux"
        )

    if runtime == "windows":
        return RuntimeEnvironment(name="windows")

    if runtime == "linux":
        return RuntimeEnvironment(
            name="linux",
            is_wsl=detect_wsl(environ=env, proc_version=proc_version),
            wsl_distro=wsl_distro,
        )

    if host_os_name == "nt":
        return RuntimeEnvironment(name="windows")

    return RuntimeEnvironment(
        name="linux",
        is_wsl=detect_wsl(environ=env, proc_version=proc_version),
        wsl_distro=wsl_distro,
    )


def find_linux_browser_executable() -> str:
    """Find a Chrome/Chromium executable commonly available on Linux."""
    for executable in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ):
        resolved = shutil.which(executable)
        if resolved:
            return resolved
    return ""
