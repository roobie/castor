"""Tests for 'casq add' command."""

import pytest
import os
import stat
from pathlib import Path
from fixtures import sample_files
from helpers.verification import (
    verify_object_exists,
    get_object_type,
    parse_tree_entries,
    count_objects,
    list_all_refs,
)


@pytest.mark.smoke
def test_add_single_regular_file(cli, initialized_store, sample_file):
    """Test adding a single regular file."""
    result = cli.add(sample_file, root=initialized_store)

    assert result.returncode == 0
    # Output should contain a hash
    hash_output = result.stdout.strip().split()[0]
    assert len(hash_output) == 64  # BLAKE3 hex length
    verify_object_exists(initialized_store, hash_output)


def test_add_file_returns_correct_hash_format(cli, initialized_store, sample_file):
    """Test that add returns valid hex hash."""
    result = cli.add(sample_file, root=initialized_store)

    hash_output = result.stdout.strip().split()[0]
    # Should be valid hex
    int(hash_output, 16)
    assert len(hash_output) == 64


def test_add_executable_file(cli, initialized_store, workspace):
    """Test adding executable file preserves executable bit."""
    exe_file = sample_files.create_executable_file(
        workspace / "script.sh", "#!/bin/bash\necho hello\n"
    )

    result = cli.add(exe_file, root=initialized_store)
    assert result.returncode == 0

    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)


def test_add_empty_file(cli, initialized_store, workspace):
    """Test adding an empty file."""
    empty_file = sample_files.create_empty_file(workspace / "empty.txt")

    result = cli.add(empty_file, root=initialized_store)

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)


def test_add_binary_file(cli, initialized_store, sample_binary):
    """Test adding a binary file."""
    result = cli.add(sample_binary, root=initialized_store)

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)
    assert get_object_type(initialized_store, hash_output) == "blob"


def test_add_file_with_unicode_name(cli, initialized_store, workspace):
    """Test adding file with unicode characters in name."""
    unicode_file = sample_files.create_sample_file(
        workspace / "café_☕.txt", "Unicode filename test"
    )

    result = cli.add(unicode_file, root=initialized_store)

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)


def test_add_file_with_spaces_in_name(cli, initialized_store, workspace):
    """Test adding file with spaces in name."""
    spaced_file = sample_files.create_sample_file(
        workspace / "file with spaces.txt", "Spaces in filename"
    )

    result = cli.add(spaced_file, root=initialized_store)

    assert result.returncode == 0


def test_add_with_ref_name(cli, initialized_store, sample_file):
    """Test adding file with --ref-name option."""
    result = cli.add(sample_file, root=initialized_store, ref_name="myref")

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]

    # Check that ref was created
    refs = list_all_refs(initialized_store)
    assert "myref" in refs
    assert refs["myref"] == hash_output


def test_add_empty_directory(cli, initialized_store, workspace):
    """Test adding an empty directory."""
    empty_dir = workspace / "empty_dir"
    empty_dir.mkdir()

    result = cli.add(empty_dir, root=initialized_store)

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)
    assert get_object_type(initialized_store, hash_output) == "tree"


def test_add_flat_directory(cli, initialized_store, sample_tree):
    """Test adding a flat directory (no subdirectories)."""
    result = cli.add(sample_tree, root=initialized_store)

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)
    assert get_object_type(initialized_store, hash_output) == "tree"


def test_add_nested_directory_tree(cli, initialized_store, nested_tree):
    """Test adding a nested directory structure."""
    result = cli.add(nested_tree, root=initialized_store)

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)
    assert get_object_type(initialized_store, hash_output) == "tree"


def test_add_directory_creates_tree_object(cli, initialized_store, sample_tree):
    """Test that adding directory creates a tree object."""
    result = cli.add(sample_tree, root=initialized_store)

    hash_output = result.stdout.strip().split()[0]
    obj_type = get_object_type(initialized_store, hash_output)
    assert obj_type == "tree"


def test_add_directory_creates_blob_objects_for_files(
    cli, initialized_store, sample_tree
):
    """Test that adding directory also creates blob objects for files."""
    initial_count = count_objects(initialized_store)

    result = cli.add(sample_tree, root=initialized_store)
    assert result.returncode == 0

    final_count = count_objects(initialized_store)
    # Should have at least 1 tree + 2 blobs (from SIMPLE_TREE)
    assert final_count >= initial_count + 3


def test_add_tree_entries_are_parseable(cli, initialized_store, sample_tree):
    """Test that tree entries can be parsed correctly."""
    result = cli.add(sample_tree, root=initialized_store)

    tree_hash = result.stdout.strip().split()[0]
    entries = parse_tree_entries(initialized_store, tree_hash)

    # SIMPLE_TREE has 2 files
    assert len(entries) == 2
    assert all(e["type"] == "blob" for e in entries)
    assert all(len(e["hash"]) == 64 for e in entries)
    assert all(len(e["name"]) > 0 for e in entries)


def test_add_tree_entries_sorted_by_name(cli, initialized_store, workspace):
    """Test that tree entries are sorted alphabetically."""
    tree_dir = sample_files.create_directory_tree(
        workspace / "sorted",
        {
            "zebra.txt": "last",
            "apple.txt": "first",
            "middle.txt": "middle",
        },
    )

    result = cli.add(tree_dir, root=initialized_store)
    tree_hash = result.stdout.strip().split()[0]

    entries = parse_tree_entries(initialized_store, tree_hash)
    names = [e["name"] for e in entries]

    assert names == sorted(names)
    assert names == ["apple.txt", "middle.txt", "zebra.txt"]


def test_add_multiple_paths_in_one_command(cli, initialized_store, workspace):
    """Test adding multiple files in a single command."""
    file1 = sample_files.create_sample_file(workspace / "file1.txt", "content1")
    file2 = sample_files.create_sample_file(workspace / "file2.txt", "content2")

    result = cli.add(file1, file2, root=initialized_store)

    assert result.returncode == 0
    # Should output multiple hashes
    lines = result.stdout.strip().split("\n")
    assert len(lines) >= 2


def test_add_same_file_twice_deduplication(cli, initialized_store, sample_file):
    """Test that adding same file twice only stores it once."""
    # First add
    result1 = cli.add(sample_file, root=initialized_store)
    hash1 = result1.stdout.strip().split()[0]
    count1 = count_objects(initialized_store)

    # Second add
    result2 = cli.add(sample_file, root=initialized_store)
    hash2 = result2.stdout.strip().split()[0]
    count2 = count_objects(initialized_store)

    # Same hash, same object count
    assert hash1 == hash2
    assert count2 == count1


def test_add_nonexistent_path_error(cli, initialized_store, workspace):
    """Test adding non-existent path fails gracefully."""
    nonexistent = workspace / "does_not_exist.txt"

    result = cli.add(nonexistent, root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_add_without_initialized_store_error(cli, casq_store, sample_file):
    """Test adding to non-initialized store fails."""
    # casq_store is not initialized
    result = cli.add(sample_file, root=casq_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_add_permission_denied_error(cli, initialized_store, workspace):
    """Test adding file without read permissions."""
    if os.name == "nt":
        pytest.skip("Permission test not reliable on Windows")

    restricted_file = sample_files.create_sample_file(
        workspace / "restricted.txt", "secret"
    )
    restricted_file.chmod(0o000)

    try:
        result = cli.add(restricted_file, root=initialized_store, expect_success=False)
        assert result.returncode != 0
    finally:
        restricted_file.chmod(0o644)


def test_add_very_long_filename(cli, initialized_store, workspace):
    """Test adding file with very long (but valid) filename."""
    # Max filename length is typically 255 bytes
    long_name = "a" * 200 + ".txt"
    long_file = sample_files.create_sample_file(
        workspace / long_name, "long filename test"
    )

    result = cli.add(long_file, root=initialized_store)

    assert result.returncode == 0


def test_add_large_file(cli, initialized_store, workspace):
    """Test adding a relatively large file (1MB)."""
    large_file = sample_files.create_binary_file(
        workspace / "large.bin",
        size=1024 * 1024,  # 1MB
        pattern=b"\xff\xee\xdd\xcc",
    )

    result = cli.add(large_file, root=initialized_store)

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)


def test_add_many_files_in_directory(cli, initialized_store, workspace):
    """Test adding directory with many files."""
    many_dir = workspace / "many"
    many_dir.mkdir()

    # Create 100 small files
    for i in range(100):
        sample_files.create_sample_file(many_dir / f"file_{i:03d}.txt", f"content {i}")

    result = cli.add(many_dir, root=initialized_store)

    assert result.returncode == 0
    tree_hash = result.stdout.strip().split()[0]
    entries = parse_tree_entries(initialized_store, tree_hash)
    assert len(entries) == 100


def test_add_deeply_nested_directory(cli, initialized_store, workspace):
    """Test adding deeply nested directory structure."""
    # Create a 10-level deep structure
    current = workspace / "deep"
    for i in range(10):
        current = current / f"level_{i}"
    current.mkdir(parents=True)
    sample_files.create_sample_file(current / "deep_file.txt", "deep content")

    result = cli.add(workspace / "deep", root=initialized_store)

    assert result.returncode == 0


def test_add_directory_with_various_file_types(cli, initialized_store, complex_tree):
    """Test adding directory with mixed file types."""
    result = cli.add(complex_tree, root=initialized_store)

    assert result.returncode == 0
    tree_hash = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, tree_hash)


def test_add_preserves_directory_mode(cli, initialized_store, workspace):
    """Test that directory mode information is preserved."""
    test_dir = workspace / "mode_test"
    test_dir.mkdir()
    sample_files.create_sample_file(test_dir / "file.txt", "content")

    result = cli.add(test_dir, root=initialized_store)

    assert result.returncode == 0
    # Mode info should be in tree entries
    tree_hash = result.stdout.strip().split()[0]
    entries = parse_tree_entries(initialized_store, tree_hash)
    assert all(e["mode"] > 0 for e in entries)


def test_add_file_mode_preserved(cli, initialized_store, workspace):
    """Test that file mode is preserved in tree entry."""
    sample_files.create_file_with_mode(workspace / "executable", "#!/bin/bash\n", 0o755)

    # Add via parent directory to get tree entry
    result = cli.add(workspace, root=initialized_store)
    tree_hash = result.stdout.strip().split()[0]

    entries = parse_tree_entries(initialized_store, tree_hash)
    exe_entry = [e for e in entries if e["name"] == "executable"][0]

    # Mode should include executable bit
    assert exe_entry["mode"] & stat.S_IXUSR != 0


def test_add_ref_name_creates_ref_file(cli, initialized_store, sample_file):
    """Test that --ref-name creates actual ref file."""
    cli.add(sample_file, root=initialized_store, ref_name="test-ref")

    ref_file = initialized_store / "refs" / "test-ref"
    assert ref_file.exists()
    assert ref_file.is_file()


def test_add_ref_name_contains_correct_hash(cli, initialized_store, sample_file):
    """Test that ref file contains the correct hash."""
    result = cli.add(sample_file, root=initialized_store, ref_name="test-ref")
    expected_hash = result.stdout.strip().split()[0]

    ref_file = initialized_store / "refs" / "test-ref"
    ref_content = ref_file.read_text().strip()

    assert expected_hash in ref_content


def test_add_updates_existing_ref(cli, initialized_store, workspace):
    """Test that adding with existing ref-name updates the ref."""
    file1 = sample_files.create_sample_file(workspace / "file1.txt", "content1")
    file2 = sample_files.create_sample_file(workspace / "file2.txt", "content2")

    # First add
    result1 = cli.add(file1, root=initialized_store, ref_name="myref")
    hash1 = result1.stdout.strip().split()[0]

    # Second add with same ref name
    result2 = cli.add(file2, root=initialized_store, ref_name="myref")
    hash2 = result2.stdout.strip().split()[0]

    # Ref should now point to hash2
    refs = list_all_refs(initialized_store)
    assert refs["myref"] == hash2
    assert hash1 != hash2


def test_add_subdirectory_also_becomes_tree(cli, initialized_store, nested_tree):
    """Test that subdirectories also become tree objects."""
    result = cli.add(nested_tree, root=initialized_store)
    root_hash = result.stdout.strip().split()[0]

    # Parse root tree
    entries = parse_tree_entries(initialized_store, root_hash)

    # Find a tree entry
    tree_entries = [e for e in entries if e["type"] == "tree"]
    assert len(tree_entries) > 0

    # Verify the subtree exists
    for entry in tree_entries:
        verify_object_exists(initialized_store, entry["hash"])


def test_add_mixed_files_and_directories(cli, initialized_store, workspace):
    """Test adding mix of files and directories."""
    file1 = sample_files.create_sample_file(workspace / "file1.txt", "content1")
    dir1 = sample_files.create_directory_tree(workspace / "dir1", {"f.txt": "in dir"})

    result = cli.add(file1, dir1, root=initialized_store)

    assert result.returncode == 0
    lines = result.stdout.strip().split("\n")
    assert len(lines) == 2


def test_add_with_dot_files(cli, initialized_store, workspace):
    """Test adding directory with hidden files (starting with dot)."""
    tree_dir = sample_files.create_directory_tree(
        workspace / "dotfiles",
        {
            ".hidden": "hidden content",
            "visible.txt": "visible content",
        },
    )

    result = cli.add(tree_dir, root=initialized_store)

    assert result.returncode == 0
    tree_hash = result.stdout.strip().split()[0]
    entries = parse_tree_entries(initialized_store, tree_hash)

    names = [e["name"] for e in entries]
    assert ".hidden" in names
    assert "visible.txt" in names


def test_add_empty_directory_creates_empty_tree(cli, initialized_store, workspace):
    """Test that empty directory creates tree with no entries."""
    empty_dir = workspace / "empty"
    empty_dir.mkdir()

    result = cli.add(empty_dir, root=initialized_store)
    tree_hash = result.stdout.strip().split()[0]

    entries = parse_tree_entries(initialized_store, tree_hash)
    assert len(entries) == 0


def test_add_single_blob_object_type(cli, initialized_store, sample_file):
    """Test that adding a file creates a blob object."""
    result = cli.add(sample_file, root=initialized_store)
    hash_output = result.stdout.strip().split()[0]

    obj_type = get_object_type(initialized_store, hash_output)
    assert obj_type == "blob"


def test_add_file_with_newlines(cli, initialized_store, workspace):
    """Test adding file with various newline styles."""
    file_with_newlines = sample_files.create_sample_file(
        workspace / "newlines.txt", "line1\nline2\r\nline3\r"
    )

    result = cli.add(file_with_newlines, root=initialized_store)

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)


def test_add_binary_file_with_null_bytes(cli, initialized_store, workspace):
    """Test adding binary file containing null bytes."""
    null_file = sample_files.create_binary_file(
        workspace / "nulls.bin", size=100, pattern=b"\x00"
    )

    result = cli.add(null_file, root=initialized_store)

    assert result.returncode == 0
    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)


def test_add_relative_path(cli, initialized_store, workspace):
    """Test adding file using relative path."""
    # Change to workspace directory for relative path
    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(workspace)
        sample_files.create_sample_file(Path("relative.txt"), "relative path test")

        result = cli.add(Path("relative.txt"), root=initialized_store)
        assert result.returncode == 0
    finally:
        os.chdir(original_cwd)


def test_add_absolute_path(cli, initialized_store, workspace):
    """Test adding file using absolute path."""
    abs_file = sample_files.create_sample_file(
        workspace / "absolute.txt", "absolute path test"
    )

    result = cli.add(abs_file.absolute(), root=initialized_store)

    assert result.returncode == 0
