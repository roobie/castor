"""Tests for 'castor init' command."""

import pytest
import os
from pathlib import Path
from helpers.verification import verify_store_structure


@pytest.mark.smoke
def test_init_default(cli, castor_store):
    """Test basic store initialization with defaults."""
    result = cli.init(root=castor_store)

    assert result.returncode == 0
    verify_store_structure(castor_store, algo="blake3")


def test_init_creates_config_file(cli, castor_store):
    """Test that init creates a config file."""
    cli.init(root=castor_store)

    config_file = castor_store / "config"
    assert config_file.exists()
    assert config_file.is_file()

    content = config_file.read_text()
    assert len(content) > 0


def test_init_creates_objects_directory(cli, castor_store):
    """Test that init creates the objects directory structure."""
    cli.init(root=castor_store)

    objects_dir = castor_store / "objects" / "blake3"
    assert objects_dir.exists()
    assert objects_dir.is_dir()


def test_init_creates_refs_directory(cli, castor_store):
    """Test that init creates the refs directory."""
    cli.init(root=castor_store)

    refs_dir = castor_store / "refs"
    assert refs_dir.exists()
    assert refs_dir.is_dir()


def test_init_with_explicit_root(cli, tmp_path):
    """Test init with explicitly specified --root path."""
    custom_root = tmp_path / "custom_store"
    custom_root.mkdir()

    result = cli.init(root=custom_root)

    assert result.returncode == 0
    verify_store_structure(custom_root)


def test_init_with_env_var(cli, tmp_path, castor_binary):
    """Test init respects CASTOR_ROOT environment variable."""
    custom_root = tmp_path / "env_store"
    custom_root.mkdir()

    env = {"CASTOR_ROOT": str(custom_root)}
    result = cli.run("init", env=env)

    assert result.returncode == 0
    verify_store_structure(custom_root)


def test_init_with_blake3_algo(cli, castor_store):
    """Test init with explicit blake3 algorithm."""
    result = cli.init(root=castor_store, algo="blake3")

    assert result.returncode == 0
    verify_store_structure(castor_store, algo="blake3")


def test_init_with_unsupported_algo(cli, castor_store):
    """Test init fails with unsupported algorithm."""
    result = cli.init(root=castor_store, algo="sha256", expect_success=False)

    assert result.returncode != 0
    assert "unsupported" in result.stderr.lower() or "unknown" in result.stderr.lower()


def test_init_nonexistent_parent_directory(cli, tmp_path):
    """Test init with parent directory that doesn't exist."""
    deep_path = tmp_path / "does" / "not" / "exist" / "store"

    # Castor may or may not create parent directories
    # If it fails, that's acceptable behavior
    result = cli.run("init", "--root", str(deep_path), expect_success=False)

    # Either succeeds and creates parents, or fails gracefully
    if result.returncode == 0:
        verify_store_structure(deep_path)
    else:
        assert len(result.stderr) > 0


def test_init_permission_denied(cli, tmp_path):
    """Test init handles permission denied gracefully."""
    if os.name == 'nt':
        pytest.skip("Permission test not reliable on Windows")

    restricted_dir = tmp_path / "restricted"
    restricted_dir.mkdir(mode=0o000)

    try:
        result = cli.init(root=restricted_dir, expect_success=False)
        assert result.returncode != 0
        # Should get permission error
    finally:
        # Restore permissions for cleanup
        restricted_dir.chmod(0o755)


def test_init_already_initialized(cli, castor_store):
    """Test init behavior when store already initialized."""
    # First initialization
    cli.init(root=castor_store)

    # Second initialization - behavior depends on implementation
    result = cli.run("init", root=castor_store, expect_success=False)

    # Either succeeds (idempotent) or fails with appropriate error
    if result.returncode != 0:
        assert len(result.stderr) > 0


def test_init_output_message(cli, castor_store):
    """Test init provides appropriate output message."""
    result = cli.init(root=castor_store)

    # Should provide some confirmation
    assert len(result.stdout) > 0 or len(result.stderr) > 0


def test_init_empty_store_has_no_objects(cli, castor_store):
    """Test newly initialized store has no objects."""
    cli.init(root=castor_store)

    from helpers.verification import count_objects
    assert count_objects(castor_store) == 0


def test_init_empty_store_has_no_refs(cli, castor_store):
    """Test newly initialized store has no refs."""
    cli.init(root=castor_store)

    refs_dir = castor_store / "refs"
    refs = list(refs_dir.iterdir())
    assert len(refs) == 0


def test_init_config_contains_algo(cli, castor_store):
    """Test config file contains algorithm information."""
    cli.init(root=castor_store, algo="blake3")

    config_file = castor_store / "config"
    content = config_file.read_text()

    # Config should mention the algorithm
    assert "blake3" in content.lower()


def test_init_with_existing_empty_directory(cli, tmp_path):
    """Test init in an existing empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = cli.init(root=empty_dir)

    assert result.returncode == 0
    verify_store_structure(empty_dir)


def test_init_creates_subdirectories_with_correct_permissions(cli, castor_store):
    """Test that created directories have reasonable permissions."""
    cli.init(root=castor_store)

    objects_dir = castor_store / "objects" / "blake3"
    refs_dir = castor_store / "refs"

    # Directories should be readable/writable/executable by owner
    assert objects_dir.stat().st_mode & 0o700 == 0o700
    assert refs_dir.stat().st_mode & 0o700 == 0o700
