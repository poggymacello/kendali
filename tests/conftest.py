import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kendali.config import DATA_DIR  # noqa: E402
from kendali.registry import Registry  # noqa: E402


@pytest.fixture(scope="session")
def registry() -> Registry:
    return Registry.load(DATA_DIR)


@pytest.fixture(scope="session")
def inbox() -> Path:
    return DATA_DIR / "invoices" / "inbox"
