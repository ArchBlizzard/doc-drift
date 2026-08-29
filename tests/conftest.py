import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# eval/ is a plain script directory, not a package; make it importable for tests
sys.path.insert(0, str(ROOT / "eval"))


@pytest.fixture
def repo_root() -> Path:
    return ROOT
