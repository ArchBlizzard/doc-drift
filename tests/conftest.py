import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# eval/ is a plain script directory and the CLIs live at the repo root;
# make both importable for tests
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def repo_root() -> Path:
    return ROOT
