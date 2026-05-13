from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


SCRIPT = Path(__file__).resolve().parent.parent.parent / "boot_recover.sh"


def _run_boot_recover(tmp_path: Path, **env_overrides: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "BOOT_RECOVERY_LOG_DIR": str(tmp_path / "logs"),
            "BOOT_RECOVERY_DATA_DIR": str(tmp_path / "data"),
            "BOOT_RECOVERY_RUN_SCAN_CMD": str(tmp_path / "run_scan_fake.sh"),
            "BOOT_RECOVERY_ENSURE_SENDER_CMD": str(tmp_path / "ensure_sender_fake.sh"),
            "BOOT_RECOVERY_SCAN_PROCESS_PATTERN": str(tmp_path / "scan_deals.py"),
            "BOOT_RECOVERY_NOW": "2026-05-11T16:30:00-03:00",
        }
    )
    env.update(env_overrides)
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=str(SCRIPT.parent),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _write_fake_cmd(path: Path, marker: Path, label: str) -> None:
    path.write_text(
        "#!/usr/bin/env bash\n"
        f"printf '%s\\n' '{label}' >> '{marker}'\n",
        encoding="utf-8",
    )
    path.chmod(0o755)


def test_boot_recover_skips_outside_active_window(tmp_path):
    marker = tmp_path / "calls.log"
    _write_fake_cmd(tmp_path / "run_scan_fake.sh", marker, "scan")
    _write_fake_cmd(tmp_path / "ensure_sender_fake.sh", marker, "sender")

    result = _run_boot_recover(
        tmp_path,
        BOOT_RECOVERY_NOW="2026-05-11T07:59:00-03:00",
    )

    assert result.returncode == 0
    assert not marker.exists()


def test_boot_recover_runs_scan_when_no_recent_scan_exists(tmp_path):
    marker = tmp_path / "calls.log"
    _write_fake_cmd(tmp_path / "run_scan_fake.sh", marker, "scan")
    _write_fake_cmd(tmp_path / "ensure_sender_fake.sh", marker, "sender")

    result = _run_boot_recover(tmp_path)

    assert result.returncode == 0
    assert marker.read_text(encoding="utf-8").splitlines() == ["sender", "scan"]


def test_boot_recover_skips_scan_when_recent_log_is_healthy(tmp_path):
    marker = tmp_path / "calls.log"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    healthy_log = logs_dir / "scan-2026-05-11.log"
    healthy_log.write_text(
        "[2026-05-11 16:15:01] Scanning for deals (min 10.0% off)...\n"
        "Cadence scan summary: 1 urgent, 1 priority, 1 normal\n",
        encoding="utf-8",
    )
    now = datetime(2026, 5, 11, 19, 30, tzinfo=timezone.utc).timestamp()
    os.utime(healthy_log, (now, now))

    _write_fake_cmd(tmp_path / "run_scan_fake.sh", marker, "scan")
    _write_fake_cmd(tmp_path / "ensure_sender_fake.sh", marker, "sender")

    result = _run_boot_recover(tmp_path)

    assert result.returncode == 0
    assert marker.read_text(encoding="utf-8").splitlines() == ["sender"]


def test_boot_recover_treats_hung_scan_as_unhealthy(tmp_path):
    marker = tmp_path / "calls.log"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    scan_process = tmp_path / "scan_deals.py"
    scan_process.write_text(
        "#!/usr/bin/env bash\n"
        "while true; do sleep 1; done\n",
        encoding="utf-8",
    )
    scan_process.chmod(0o755)

    proc = subprocess.Popen([str(scan_process)], cwd=str(tmp_path))
    try:
        time.sleep(2)
        _write_fake_cmd(tmp_path / "run_scan_fake.sh", marker, "scan")
        _write_fake_cmd(tmp_path / "ensure_sender_fake.sh", marker, "sender")

        result = _run_boot_recover(
            tmp_path,
            BOOT_RECOVERY_SCAN_MAX_RUNTIME_SECONDS="1",
        )

        assert result.returncode == 0
        assert marker.read_text(encoding="utf-8").splitlines() == ["sender", "scan"]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
