from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent.parent / "run_scan.sh"


def _shell_path(path: Path) -> str:
    return path.resolve().as_posix()


def _run_scan(tmp_path: Path, *args: str, **env_overrides: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "SCAN_RUN_PYTHON": Path(sys.executable).resolve().as_posix(),
            "SCAN_RUN_SCRIPT": _shell_path(tmp_path / "scan_fake.py"),
            "SCAN_RUN_LOG_DIR": _shell_path(tmp_path / "logs"),
            "SCAN_RUN_DATA_DIR": _shell_path(tmp_path / "data"),
            "SCAN_RUN_LOCK_DIR": _shell_path(tmp_path / "data" / "scan.lock"),
        }
    )
    env.update(env_overrides)
    return subprocess.run(
        ["bash", _shell_path(SCRIPT), *args],
        cwd=str(SCRIPT.parent),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_fake_scan(path: Path, marker: Path, *, sleep_seconds: float = 0.0) -> None:
    payload = (
        "from __future__ import annotations\n"
        "import json\n"
        "import sys\n"
        "import time\n"
        f"marker = {str(marker)!r}\n"
        f"sleep_seconds = {sleep_seconds!r}\n"
        "with open(marker, 'a', encoding='utf-8') as handle:\n"
        "    handle.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sleep_seconds:\n"
        "    time.sleep(sleep_seconds)\n"
    )
    path.write_text(payload, encoding="utf-8")


def test_run_scan_passes_expected_scan_arguments(tmp_path):
    marker = tmp_path / "calls.jsonl"
    _write_fake_scan(tmp_path / "scan_fake.py", marker)

    result = _run_scan(
        tmp_path,
        PRICE_ALERT_SCAN_PROFILE="beauty",
        PRICE_ALERT_SCAN_CATEGORIES="beleza_perfumes",
    )

    assert result.returncode == 0
    captured_args = json.loads(marker.read_text(encoding="utf-8").splitlines()[0])
    assert captured_args == [
        "--all",
        "--profile",
        "beauty",
        "--query-categories",
        "beleza_perfumes",
        "--scan-only",
        "--min-discount",
        "10",
        "--max-results",
        "8",
    ]


def test_run_scan_skips_when_previous_scan_still_holds_lock(tmp_path):
    marker = tmp_path / "calls.jsonl"
    logs_dir = tmp_path / "logs"
    _write_fake_scan(tmp_path / "scan_fake.py", marker, sleep_seconds=2.0)

    env = os.environ.copy()
    env.update(
        {
            "TZ": "America/Sao_Paulo",
            "SCAN_RUN_PYTHON": Path(sys.executable).resolve().as_posix(),
            "SCAN_RUN_SCRIPT": _shell_path(tmp_path / "scan_fake.py"),
            "SCAN_RUN_LOG_DIR": _shell_path(logs_dir),
            "SCAN_RUN_DATA_DIR": _shell_path(tmp_path / "data"),
            "SCAN_RUN_LOCK_DIR": _shell_path(tmp_path / "data" / "scan.lock"),
        }
    )

    proc = subprocess.Popen(
        ["bash", _shell_path(SCRIPT)],
        cwd=str(SCRIPT.parent),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        time.sleep(0.5)
        result = subprocess.run(
            ["bash", _shell_path(SCRIPT)],
            cwd=str(SCRIPT.parent),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        log_file = logs_dir / f"scan-{time.strftime('%Y-%m-%d')}.log"
        assert result.returncode == 0
        assert "Scan already running; skipping this trigger." in log_file.read_text(encoding="utf-8")
    finally:
        proc.wait(timeout=10)

    captured_lines = marker.read_text(encoding="utf-8").splitlines()
    assert len(captured_lines) == 1
