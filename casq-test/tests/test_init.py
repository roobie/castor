"""Tests for 'casq init' command."""

import pytest
import os
from helpers.verification import verify_store_structure


@pytest.mark.smoke
def test_init_default(cli, casq_store):
    """Test basic store initialization with defaults."""
    result = cli.init(root=casq_store)

    assert result.returncode == 0
    verify_store_structure(casq_store)


def test_init_creates_config_file(cli, casq_store):
    """Test that init creates a config file."""
    cli.init(root=casq_store)

    config_file = casq_store / "config"
    assert config_file.exists()
    assert config_file.is_file()

    content = config_file.read_text()
    assert len(content) > 0


def test_init_creates_objects_directory(cli, casq_store):
    """Test that init creates the objects directory structure."""
    cli.init(root=casq_store)

    objects_dir = casq_store / "objects" / "blake3-256"
    assert objects_dir.exists()
    assert objects_dir.is_dir()


def test_init_creates_refs_directory(cli, casq_store):
    """Test that init creates the refs directory."""
    cli.init(root=casq_store)

    refs_dir = casq_store / "refs"
    assert refs_dir.exists()
    assert refs_dir.is_dir()


def test_init_with_explicit_root(cli, tmp_path):
    """Test init with explicitly specified --root path."""
    custom_root = tmp_path / "custom_store"
    custom_root.mkdir()

    result = cli.init(root=custom_root)

    assert result.returncode == 0
    verify_store_structure(custom_root)


def test_init_with_env_var(cli, tmp_path, casq_binary):
    """Test init respects CASTOR_ROOT environment variable."""
    custom_root = tmp_path / "env_store"
    custom_root.mkdir()

    env = {"CASTOR_ROOT": str(custom_root)}
    result = cli.run("init", env=env)

    assert result.returncode == 0
    verify_store_structure(custom_root)


def test_init_with_blake3_algo(cli, casq_store):
    """Test init with explicit blake3 algorithm."""
    result = cli.init(root=casq_store, algo="blake3")

    assert result.returncode == 0
    verify_store_structure(casq_store)


def test_init_with_unsupported_algo(cli, casq_store):
    """Test init fails with unsupported algorithm."""
    result = cli.init(root=casq_store, algo="sha256", expect_success=False)

    assert result.returncode != 0
    assert "unsupported" in result.stderr.lower() or "unknown" in result.stderr.lower()


def test_init_nonexistent_parent_directory(cli, tmp_path):
    """Test init with parent directory that doesn't exist."""
    deep_path = tmp_path / "does" / "not" / "exist" / "store"

    # casq may or may not create parent directories
    # If it fails, that's acceptable behavior
    result = cli.run("init", "--root", str(deep_path), expect_success=False)

    # Either succeeds and creates parents, or fails gracefully
    if result.returncode == 0:
        verify_store_structure(deep_path)
    else:
        assert len(result.stderr) > 0


def test_init_permission_denied(cli, tmp_path):
    """Test init handles permission denied gracefully."""
    if os.name == "nt":
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


def test_init_already_initialized(cli, casq_store):
    """Test init behavior when store already initialized."""
    # First initialization
    cli.init(root=casq_store)

    # Second initialization - behavior depends on implementation
    result = cli.run("init", root=casq_store, expect_success=False)

    # Either succeeds (idempotent) or fails with appropriate error
    if result.returncode != 0:
        assert len(result.stderr) > 0


def test_init_output_message(cli, casq_store):
    """Test init provides appropriate output message."""
    result = cli.init(root=casq_store)

    # Confirmation message should go to stderr in text mode
    assert len(result.stderr) > 0


def test_init_empty_store_has_no_objects(cli, casq_store):
    """Test newly initialized store has no objects."""
    cli.init(root=casq_store)

    from helpers.verification import count_objects

    assert count_objects(casq_store) == 0


def test_init_empty_store_has_no_refs(cli, casq_store):
    """Test newly initialized store has no refs."""
    cli.init(root=casq_store)

    refs_dir = casq_store / "refs"
    refs = list(refs_dir.iterdir())
    assert len(refs) == 0


def test_init_config_contains_algo(cli, casq_store):
    """Test config file contains algorithm information."""
    cli.init(root=casq_store, algo="blake3")

    config_file = casq_store / "config"
    content = config_file.read_text()

    # Config should mention the algorithm (blake3 or blake3-256)
    assert "blake3" in content.lower()


def test_init_with_existing_empty_directory(cli, tmp_path):
    """Test init in an existing empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = cli.init(root=empty_dir)

    assert result.returncode == 0
    verify_store_structure(empty_dir)


def test_init_creates_subdirectories_with_correct_permissions(cli, casq_store):
    """Test that created directories have reasonable permissions."""
    cli.init(root=casq_store)

    objects_dir = casq_store / "objects" / "blake3-256"
    refs_dir = casq_store / "refs"

    # Directories should be readable/writable/executable by owner
    assert objects_dir.stat().st_mode & 0o700 == 0o700
    assert refs_dir.stat().st_mode & 0o700 == 0o700
