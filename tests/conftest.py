"""Shared pytest fixtures."""

from pathlib import Path

import pytest

from tests.helpers import PROJECT_ROOT


@pytest.fixture
def project_root() -> Path:
    """Return the repository root."""
    return PROJECT_ROOT
