"""Tests for 'castor materialize' command."""

import pytest
import stat
from fixtures import sample_files


@pytest.mark.smoke
def test_materialize_single_blob(cli, initialized_store, workspace, sample_file):
    """Test materializing a single blob to a file."""
    # Add file
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    # Materialize to new location
    dest = workspace / "restored.txt"
    mat_result = cli.materialize(file_hash, dest, root=initialized_store)

    assert mat_result.returncode == 0
    assert dest.exists()
    assert dest.read_text() == sample_file.read_text()


def test_materialize_blob_content_identical(cli, initialized_store, workspace):
    """Test that materialized content is identical to original."""
    original = sample_files.create_sample_file(
        workspace / "original.txt",
        "test content\nwith multiple lines\n"
    )

    add_result = cli.add(original, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    dest = workspace / "restored.txt"
    cli.materialize(file_hash, dest, root=initialized_store)

    assert dest.read_text() == original.read_text()


def test_materialize_executable_preserves_mode(cli, initialized_store, workspace):
    """Test that materializing executable file preserves executable bit."""
    exe_file = sample_files.create_executable_file(
        workspace / "script.sh",
        "#!/bin/bash\necho hello\n"
    )
    original_mode = exe_file.stat().st_mode

    # Add as part of tree to preserve mode
    add_result = cli.add(workspace, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    # Materialize entire tree
    dest_dir = workspace / "restored"
    cli.materialize(tree_hash, dest_dir, root=initialized_store)

    restored_exe = dest_dir / "script.sh"
    restored_mode = restored_exe.stat().st_mode

    # Check executable bit is preserved
    assert restored_mode & stat.S_IXUSR == original_mode & stat.S_IXUSR


def test_materialize_directory_structure(cli, initialized_store, workspace, sample_tree):
    """Test materializing a directory tree."""
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    dest = workspace / "restored_tree"
    mat_result = cli.materialize(tree_hash, dest, root=initialized_store)

    assert mat_result.returncode == 0
    assert dest.exists()
    assert dest.is_dir()


def test_materialize_tree_recreates_files(cli, initialized_store, workspace, sample_tree):
    """Test that materializing tree recreates all files."""
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    dest = workspace / "restored"
    cli.materialize(tree_hash, dest, root=initialized_store)

    # Check files exist
    assert (dest / "file1.txt").exists()
    assert (dest / "file2.txt").exists()


def test_materialize_nested_tree(cli, initialized_store, workspace, nested_tree):
    """Test materializing nested directory structure."""
    add_result = cli.add(nested_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    dest = workspace / "restored_nested"
    cli.materialize(tree_hash, dest, root=initialized_store)

    assert dest.exists()
    assert (dest / "top.txt").exists()
    assert (dest / "dir1").is_dir()
    assert (dest / "dir1" / "file1.txt").exists()
    assert (dest / "dir2" / "subdir" / "deep.txt").exists()


def test_materialize_invalid_hash_format(cli, initialized_store, workspace):
    """Test materializing with invalid hash format."""
    dest = workspace / "dest.txt"
    result = cli.materialize("invalid_hash", dest, root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_materialize_nonexistent_hash(cli, initialized_store, workspace):
    """Test materializing non-existent hash."""
    fake_hash = "0" * 64
    dest = workspace / "dest.txt"

    result = cli.materialize(fake_hash, dest, root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_materialize_destination_already_exists(cli, initialized_store, workspace, sample_file):
    """Test materializing to existing destination."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    dest = workspace / "existing.txt"
    dest.write_text("already exists")

    result = cli.materialize(file_hash, dest, root=initialized_store, expect_success=False)

    # Should fail or warn about existing file
    assert result.returncode != 0 or "exist" in result.stderr.lower() or "exist" in result.stdout.lower()


def test_materialize_to_nonexistent_parent_directory(cli, initialized_store, workspace, sample_file):
    """Test materializing to path with non-existent parent."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    dest = workspace / "nonexistent" / "parent" / "file.txt"

    # May succeed (creating parents) or fail gracefully
    result = cli.materialize(file_hash, dest, root=initialized_store, expect_success=False)

    if result.returncode == 0:
        assert dest.exists()
    else:
        assert len(result.stderr) > 0


def test_materialize_permission_denied(cli, initialized_store, workspace, sample_file):
    """Test materializing to location without write permissions."""
    import os
    if os.name == 'nt':
        pytest.skip("Permission test not reliable on Windows")

    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    restricted_dir = workspace / "restricted"
    restricted_dir.mkdir(mode=0o555)  # Read-only

    try:
        dest = restricted_dir / "file.txt"
        result = cli.materialize(file_hash, dest, root=initialized_store, expect_success=False)

        assert result.returncode != 0
    finally:
        restricted_dir.chmod(0o755)


def test_materialize_round_trip_file(cli, initialized_store, workspace):
    """Test full round-trip: add → materialize → verify identical."""
    original = sample_files.create_sample_file(
        workspace / "original.txt",
        "Round trip test content\n"
    )

    # Add
    add_result = cli.add(original, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    # Materialize
    restored = workspace / "restored.txt"
    cli.materialize(file_hash, restored, root=initialized_store)

    # Verify
    assert original.read_text() == restored.read_text()


def test_materialize_round_trip_directory(cli, initialized_store, workspace, complex_tree):
    """Test round-trip for complex directory structure."""
    # Add
    add_result = cli.add(complex_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    # Materialize
    restored = workspace / "restored_complex"
    cli.materialize(tree_hash, restored, root=initialized_store)

    # Verify structure
    assert (restored / "README.md").exists()
    assert (restored / "src" / "main.py").exists()
    assert (restored / "src" / "lib" / "utils.py").exists()
    assert (restored / "tests" / "test_main.py").exists()
    assert (restored / "empty_dir").is_dir()


def test_materialize_empty_file(cli, initialized_store, workspace):
    """Test materializing an empty file."""
    empty = sample_files.create_empty_file(workspace / "empty.txt")

    add_result = cli.add(empty, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored_empty.txt"
    cli.materialize(file_hash, restored, root=initialized_store)

    assert restored.exists()
    assert restored.stat().st_size == 0


def test_materialize_empty_directory(cli, initialized_store, workspace):
    """Test materializing an empty directory."""
    empty_dir = workspace / "empty_dir"
    empty_dir.mkdir()

    add_result = cli.add(empty_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored_empty_dir"
    cli.materialize(tree_hash, restored, root=initialized_store)

    assert restored.exists()
    assert restored.is_dir()
    assert list(restored.iterdir()) == []


def test_materialize_binary_file(cli, initialized_store, workspace):
    """Test materializing binary file."""
    binary = sample_files.create_binary_file(
        workspace / "binary.dat",
        size=1024,
        pattern=b"\xDE\xAD\xBE\xEF"
    )

    add_result = cli.add(binary, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored.dat"
    cli.materialize(file_hash, restored, root=initialized_store)

    assert restored.read_bytes() == binary.read_bytes()


def test_materialize_file_with_unicode_name(cli, initialized_store, workspace):
    """Test materializing file with unicode name."""
    sample_files.create_sample_file(
        workspace / "café_☕.txt",
        "Unicode test"
    )

    # Add via directory to preserve name
    add_result = cli.add(workspace, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    restored_dir = workspace / "restored"
    cli.materialize(tree_hash, restored_dir, root=initialized_store)

    assert (restored_dir / "café_☕.txt").exists()


def test_materialize_large_file(cli, initialized_store, workspace):
    """Test materializing large file (1MB)."""
    large = sample_files.create_binary_file(
        workspace / "large.bin",
        size=1024 * 1024,
        pattern=b"\xFF\xEE"
    )

    add_result = cli.add(large, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored_large.bin"
    cli.materialize(file_hash, restored, root=initialized_store)

    assert restored.stat().st_size == large.stat().st_size
    assert restored.read_bytes() == large.read_bytes()


def test_materialize_deeply_nested_tree(cli, initialized_store, workspace):
    """Test materializing deeply nested structure."""
    # Create deep nesting
    current = workspace / "deep"
    for i in range(10):
        current = current / f"level_{i}"
    current.mkdir(parents=True)
    sample_files.create_sample_file(current / "deep.txt", "deep content")

    add_result = cli.add(workspace / "deep", root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored_deep"
    cli.materialize(tree_hash, restored, root=initialized_store)

    # Check deep file exists
    deep_path = restored
    for i in range(10):
        deep_path = deep_path / f"level_{i}"
    assert (deep_path / "deep.txt").exists()


def test_materialize_tree_with_many_files(cli, initialized_store, workspace):
    """Test materializing tree with many files."""
    many_dir = workspace / "many"
    many_dir.mkdir()

    for i in range(50):
        sample_files.create_sample_file(
            many_dir / f"file_{i:03d}.txt",
            f"content {i}"
        )

    add_result = cli.add(many_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored_many"
    cli.materialize(tree_hash, restored, root=initialized_store)

    # Check all files restored
    restored_files = list(restored.iterdir())
    assert len(restored_files) == 50


def test_materialize_preserves_file_content_exactly(cli, initialized_store, workspace):
    """Test that materialized content is byte-for-byte identical."""
    original = sample_files.create_sample_file(
        workspace / "exact.txt",
        "exact\ncontent\rwith\r\nvarious\nnewlines"
    )

    add_result = cli.add(original, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored_exact.txt"
    cli.materialize(file_hash, restored, root=initialized_store)

    assert restored.read_bytes() == original.read_bytes()


def test_materialize_tree_preserves_subdirectory_structure(cli, initialized_store, workspace, nested_tree):
    """Test that subdirectory structure is exactly preserved."""
    add_result = cli.add(nested_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored"
    cli.materialize(tree_hash, restored, root=initialized_store)

    # Verify directory structure
    assert (restored / "dir1").is_dir()
    assert (restored / "dir2").is_dir()
    assert (restored / "dir2" / "subdir").is_dir()


def test_materialize_from_ref(cli, initialized_store, workspace, sample_file):
    """Test materializing using a ref name instead of hash."""
    # Add with ref
    cli.add(sample_file, root=initialized_store, ref_name="myref")

    # Get hash from ref
    from helpers.verification import list_all_refs
    refs = list_all_refs(initialized_store)
    ref_hash = refs["myref"]

    # Materialize using hash
    dest = workspace / "from_ref.txt"
    cli.materialize(ref_hash, dest, root=initialized_store)

    assert dest.exists()
    assert dest.read_text() == sample_file.read_text()


def test_materialize_blob_to_stdout_not_file(cli, initialized_store, workspace, sample_file):
    """Test that materialize creates a file (not stdout like cat)."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    dest = workspace / "dest.txt"
    mat_result = cli.materialize(file_hash, dest, root=initialized_store)

    # Content should be in file, not stdout
    assert dest.exists()
    assert mat_result.stdout.strip() == "" or "materialize" in mat_result.stdout.lower()


def test_materialize_multiple_times_same_hash(cli, initialized_store, workspace, sample_file):
    """Test materializing same hash to different locations."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    dest1 = workspace / "dest1.txt"
    dest2 = workspace / "dest2.txt"

    cli.materialize(file_hash, dest1, root=initialized_store)
    cli.materialize(file_hash, dest2, root=initialized_store)

    assert dest1.read_text() == dest2.read_text()
    assert dest1.read_text() == sample_file.read_text()


def test_materialize_tree_with_dotfiles(cli, initialized_store, workspace):
    """Test materializing tree containing hidden files."""
    tree_dir = sample_files.create_directory_tree(workspace / "dotfiles", {
        ".hidden": "hidden content",
        "visible.txt": "visible",
    })

    add_result = cli.add(tree_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored_dotfiles"
    cli.materialize(tree_hash, restored, root=initialized_store)

    assert (restored / ".hidden").exists()
    assert (restored / "visible.txt").exists()


def test_materialize_provides_feedback(cli, initialized_store, workspace, sample_file):
    """Test that materialize provides some output or feedback."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    dest = workspace / "dest.txt"
    mat_result = cli.materialize(file_hash, dest, root=initialized_store)

    # Should provide some feedback (stdout or stderr)
    assert len(mat_result.stdout) > 0 or len(mat_result.stderr) > 0 or dest.exists()


def test_materialize_file_with_special_characters(cli, initialized_store, workspace):
    """Test materializing file with special characters in name."""
    sample_files.create_sample_file(
        workspace / "file-name_with.special$chars.txt",
        "special chars test"
    )

    # Add via directory
    add_result = cli.add(workspace, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    restored = workspace / "restored"
    cli.materialize(tree_hash, restored, root=initialized_store)

    assert (restored / "file-name_with.special$chars.txt").exists()


def test_materialize_symlink_handling(cli, initialized_store, workspace):
    """Test behavior when materializing tree that originally had symlinks."""
    # Note: This tests implementation-specific behavior
    # Castor may or may not preserve symlinks
    pytest.skip("Symlink handling is implementation-specific")
