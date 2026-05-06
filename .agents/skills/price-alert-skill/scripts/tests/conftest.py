from __future__ import annotations

import os
import shutil
import stat
import sys
import uuid
from pathlib import Path

import pytest


TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
SKILL_ROOT = SCRIPTS_DIR.parent
REPO_ROOT = SKILL_ROOT.parents[2]

os.environ.setdefault("PRICE_ALERT_SKILL_HOME", str(SKILL_ROOT))
repo_root_str = str(REPO_ROOT)
if repo_root_str not in sys.path:
    sys.path.insert(0, repo_root_str)

TMP_ROOT = REPO_ROOT / ".pytest-tmp" / "skill-tests"
TMP_ROOT.mkdir(parents=True, exist_ok=True)
try:
    os.chmod(TMP_ROOT, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
except OSError:
    pass
os.environ["TMP"] = str(TMP_ROOT)
os.environ["TEMP"] = str(TMP_ROOT)
os.environ["TMPDIR"] = str(TMP_ROOT)


@pytest.fixture
def tmp_path():
    temp_path = TMP_ROOT / f"tmp-{uuid.uuid4().hex}"
    temp_path.mkdir(parents=True, exist_ok=False)
    try:
        os.chmod(temp_path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
    except OSError:
        pass
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path, ignore_errors=True)
