"""
Pytest configuration and shared fixtures for casq black-box tests.
"""

import os
import subprocess
from pathlib import Path
from typing import Tuple

import pytest

# Project root (one level up from tests/)
ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def casq_bin() -> Path:
    """Ensure casq is built and return path to binary."""
    bin_path = ROOT / "target" / "debug" / "casq"

    # Build if binary doesn't exist
    if not bin_path.exists():
        print("\nBuilding casq binary...")
        subprocess.check_call(["cargo", "build"], cwd=ROOT)

    assert bin_path.exists(), f"Binary not found at {bin_path}"
    return bin_path


@pytest.fixture
def casq_env(tmp_path, casq_bin):
    """
    Return (binary_path, env, root_dir) for use in tests.

    Each test gets an isolated temporary store via CASQ_ROOT env var.
    """
    root = tmp_path / "casq-store"
    env = os.environ.copy()
    env["CASQ_ROOT"] = str(root)

    return casq_bin, env, root
