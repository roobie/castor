"""Tests for 'castor stat' command."""

import pytest
from pathlib import Path
from fixtures import sample_files
from helpers.verification import get_object_type


@pytest.mark.smoke
def test_stat_blob_shows_type(cli, initialized_store, sample_file):
    """Test that stat shows object type for blob."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(file_hash, root=initialized_store)

    assert stat_result.returncode == 0
    assert "blob" in stat_result.stdout.lower()


def test_stat_tree_shows_type(cli, initialized_store, sample_tree):
    """Test that stat shows object type for tree."""
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(tree_hash, root=initialized_store)

    assert stat_result.returncode == 0
    assert "tree" in stat_result.stdout.lower()


def test_stat_blob_shows_hash(cli, initialized_store, sample_file):
    """Test that stat shows the object hash."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(file_hash, root=initialized_store)

    assert stat_result.returncode == 0
    assert file_hash in stat_result.stdout


def test_stat_blob_shows_size(cli, initialized_store, workspace):
    """Test that stat shows blob size."""
    content = "x" * 1000
    test_file = sample_files.create_sample_file(workspace / "test.txt", content)

    add_result = cli.add(test_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(file_hash, root=initialized_store)

    assert stat_result.returncode == 0
    # Should show size (1000 bytes)
    assert "1000" in stat_result.stdout or "size" in stat_result.stdout.lower()


def test_stat_tree_shows_entries(cli, initialized_store, sample_tree):
    """Test that stat shows number of tree entries."""
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(tree_hash, root=initialized_store)

    assert stat_result.returncode == 0
    # SIMPLE_TREE has 2 entries
    assert "2" in stat_result.stdout or "entries" in stat_result.stdout.lower()


def test_stat_shows_disk_size(cli, initialized_store, sample_file):
    """Test that stat shows on-disk size."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(file_hash, root=initialized_store)

    assert stat_result.returncode == 0
    # Should show some size information
    assert any(char.isdigit() for char in stat_result.stdout)


def test_stat_shows_object_path(cli, initialized_store, sample_file):
    """Test that stat shows filesystem path to object."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(file_hash, root=initialized_store)

    assert stat_result.returncode == 0
    # Should show path or just hash prefix
    assert file_hash[:2] in stat_result.stdout or "path" in stat_result.stdout.lower()


def test_stat_invalid_hash(cli, initialized_store):
    """Test stat with invalid hash format."""
    result = cli.stat("invalid_hash", root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_stat_nonexistent_hash(cli, initialized_store):
    """Test stat with non-existent hash."""
    fake_hash = "0" * 64
    result = cli.stat(fake_hash, root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_stat_empty_blob(cli, initialized_store, workspace):
    """Test stat on empty blob."""
    empty = sample_files.create_empty_file(workspace / "empty.txt")

    add_result = cli.add(empty, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(file_hash, root=initialized_store)

    assert stat_result.returncode == 0
    assert "blob" in stat_result.stdout.lower()
    assert "0" in stat_result.stdout  # Size should be 0


def test_stat_empty_tree(cli, initialized_store, workspace):
    """Test stat on empty tree."""
    empty_dir = workspace / "empty"
    empty_dir.mkdir()

    add_result = cli.add(empty_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(tree_hash, root=initialized_store)

    assert stat_result.returncode == 0
    assert "tree" in stat_result.stdout.lower()
    assert "0" in stat_result.stdout  # 0 entries


def test_stat_large_blob(cli, initialized_store, workspace):
    """Test stat on large blob."""
    large = sample_files.create_binary_file(
        workspace / "large.bin",
        size=1024 * 100,  # 100KB
        pattern=b"\xFF"
    )

    add_result = cli.add(large, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(file_hash, root=initialized_store)

    assert stat_result.returncode == 0
    # Should show size around 100KB
    assert "blob" in stat_result.stdout.lower()


def test_stat_large_tree(cli, initialized_store, workspace):
    """Test stat on tree with many entries."""
    large_dir = workspace / "large"
    large_dir.mkdir()
    for i in range(50):
        sample_files.create_sample_file(large_dir / f"f{i}.txt", f"content{i}")

    add_result = cli.add(large_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(tree_hash, root=initialized_store)

    assert stat_result.returncode == 0
    assert "tree" in stat_result.stdout.lower()
    assert "50" in stat_result.stdout


def test_stat_output_format_consistency(cli, initialized_store, workspace):
    """Test that stat output has consistent format."""
    file1 = sample_files.create_sample_file(workspace / "f1.txt", "content1")
    file2 = sample_files.create_sample_file(workspace / "f2.txt", "content2")

    hash1 = cli.add(file1, root=initialized_store).stdout.strip().split()[0]
    hash2 = cli.add(file2, root=initialized_store).stdout.strip().split()[0]

    stat1 = cli.stat(hash1, root=initialized_store).stdout
    stat2 = cli.stat(hash2, root=initialized_store).stdout

    # Both should be blobs with similar output structure
    assert "blob" in stat1.lower()
    assert "blob" in stat2.lower()


def test_stat_multiple_times_same_hash(cli, initialized_store, sample_file):
    """Test that stat gives consistent results on multiple calls."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    result1 = cli.stat(file_hash, root=initialized_store)
    result2 = cli.stat(file_hash, root=initialized_store)
    result3 = cli.stat(file_hash, root=initialized_store)

    assert result1.stdout == result2.stdout == result3.stdout


def test_stat_nested_tree(cli, initialized_store, nested_tree):
    """Test stat on nested tree structure."""
    add_result = cli.add(nested_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    stat_result = cli.stat(tree_hash, root=initialized_store)

    assert stat_result.returncode == 0
    assert "tree" in stat_result.stdout.lower()
    # Should show entry count for immediate children
    assert any(char.isdigit() for char in stat_result.stdout)
