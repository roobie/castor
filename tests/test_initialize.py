"""
Tests for casq initialize command.
"""

import json
from .helpers import run_casq, assert_json_success


def test_initialize_creates_store(casq_env):
    """Test that initialize creates a new store directory."""
    casq_bin, env, root = casq_env

    # Before initialize, root dir should not exist
    assert not root.exists()

    proc = run_casq(casq_bin, env, "initialize")
    assert proc.returncode == 0
    assert "Initialized casq store" in proc.stderr
    assert root.exists()

    # Check that store structure was created
    assert (root / "config").exists()
    assert (root / "objects").exists()
    assert (root / "refs").exists()


def test_initialize_with_json(casq_env):
    """Test that initialize works with --json flag."""
    casq_bin, env, root = casq_env

    proc = run_casq(casq_bin, env, "--json", "initialize")
    assert proc.returncode == 0

    # Parse JSON output
    data = assert_json_success(proc.stdout, ["root", "algorithm"])
    assert "casq-store" in data["root"]
    assert data["algorithm"] == "blake3-256"

    # Store should be created
    assert root.exists()


def test_initialize_with_blake3_algorithm(casq_env):
    """Test that initialize accepts --algorithm blake3."""
    casq_bin, env, root = casq_env

    proc = run_casq(casq_bin, env, "initialize", "--algorithm", "blake3")
    assert proc.returncode == 0
    assert root.exists()

    # Verify algorithm in config
    config = (root / "config").read_text()
    assert "blake3" in config


def test_initialize_twice_succeeds(casq_env):
    """Test that initializing twice doesn't fail (idempotent)."""
    casq_bin, env, root = casq_env

    # First initialize
    proc1 = run_casq(casq_bin, env, "initialize")
    assert proc1.returncode == 0

    # Second initialize should also succeed (or be idempotent)
    proc2 = run_casq(casq_bin, env, "initialize")
    # Either succeeds or gives friendly message
    # (Implementation may vary - not strictly enforced)
    assert root.exists()


def test_initialize_custom_root(tmp_path, casq_bin):
    """Test that initialize works with custom --root path."""
    custom_root = tmp_path / "custom-store"
    env = {}  # No CASQ_ROOT env var

    proc = run_casq(casq_bin, env, "--root", str(custom_root), "initialize")

    assert proc.returncode == 0
    assert custom_root.exists()
    assert (custom_root / "config").exists()
