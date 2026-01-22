"""Edge case tests for unusual scenarios."""

import pytest
from fixtures import sample_files
from helpers.verification import count_objects


@pytest.mark.edge_case
def test_empty_store_operations(cli, initialized_store):
    """Test various operations on completely empty store."""
    # Store is initialized but has no objects

    # GC should succeed
    assert cli.gc(root=initialized_store).returncode == 0

    # Refs list should succeed
    assert cli.refs_list(root=initialized_store).returncode == 0

    # Ls (refs) should succeed
    assert cli.ls(root=initialized_store).returncode == 0


@pytest.mark.edge_case
def test_maximum_filename_length(cli, initialized_store, workspace):
    """Test handling of maximum filename length (255 bytes)."""
    # Most filesystems support 255 byte filenames
    max_name = "a" * 255 + ".txt"

    try:
        max_file = sample_files.create_sample_file(workspace / max_name, "max length test")
        result = cli.add(max_file, root=initialized_store)

        # Should either succeed or fail gracefully
        assert result.returncode == 0 or len(result.stderr) > 0
    except OSError:
        # Filesystem might not support this length
        pytest.skip("Filesystem doesn't support 255-char filenames")


@pytest.mark.edge_case
@pytest.mark.slow
def test_deep_directory_nesting(cli, initialized_store, workspace):
    """Test handling of deeply nested directories."""
    # Create 100-level deep nesting
    current = workspace / "deep"
    for i in range(100):
        current = current / f"level{i}"

    try:
        current.mkdir(parents=True)
        sample_files.create_sample_file(current / "deep.txt", "very deep")

        result = cli.add(workspace / "deep", root=initialized_store)

        # Should either succeed or fail gracefully
        if result.returncode == 0:
            hash_val = result.stdout.strip().split()[0]
            from helpers.verification import verify_object_exists
            verify_object_exists(initialized_store, hash_val)
        else:
            # Graceful failure is acceptable
            assert len(result.stderr) > 0

    except OSError:
        # Path too long for filesystem
        pytest.skip("Filesystem path length limit reached")


@pytest.mark.edge_case
def test_special_characters_in_filenames(cli, initialized_store, workspace):
    """Test handling of special characters in filenames."""
    special_chars = [
        "file-with-dash.txt",
        "file_with_underscore.txt",
        "file.multiple.dots.txt",
        "file with spaces.txt",
        "file$dollar.txt",
        "file@at.txt",
    ]

    for name in special_chars:
        try:
            file = sample_files.create_sample_file(workspace / name, f"content of {name}")
            result = cli.add(file, root=initialized_store)

            # Should handle gracefully
            if result.returncode != 0:
                assert len(result.stderr) > 0

        except (OSError, ValueError):
            # Some chars might not be allowed by OS
            pass


@pytest.mark.edge_case
@pytest.mark.slow
def test_large_file_handling(cli, initialized_store, workspace):
    """Test handling of large file (100MB)."""
    large_size = 100 * 1024 * 1024  # 100MB

    try:
        large_file = sample_files.create_binary_file(
            workspace / "large.bin",
            size=large_size,
            pattern=b"\xFF"
        )

        result = cli.add(large_file, root=initialized_store)

        if result.returncode == 0:
            hash_val = result.stdout.strip().split()[0]
            from helpers.verification import verify_object_exists
            verify_object_exists(initialized_store, hash_val)
        else:
            # Acceptable to have limits
            assert len(result.stderr) > 0

    except MemoryError:
        pytest.skip("Not enough memory for 100MB file test")


@pytest.mark.edge_case
@pytest.mark.slow
def test_many_small_files(cli, initialized_store, workspace):
    """Test handling of directory with many small files (1000+)."""
    many_dir = workspace / "many"
    many_dir.mkdir()

    # Create 1000 small files
    for i in range(1000):
        sample_files.create_sample_file(many_dir / f"file{i:04d}.txt", f"content{i}")

    result = cli.add(many_dir, root=initialized_store)

    if result.returncode == 0:
        tree_hash = result.stdout.strip().split()[0]
        from helpers.verification import verify_object_exists, parse_tree_entries
        verify_object_exists(initialized_store, tree_hash)

        # Verify tree has all entries
        entries = parse_tree_entries(initialized_store, tree_hash)
        assert len(entries) == 1000
    else:
        # Acceptable to have limits
        assert len(result.stderr) > 0


@pytest.mark.edge_case
def test_zero_byte_files(cli, initialized_store, workspace):
    """Test multiple zero-byte files deduplicate correctly."""
    # Create multiple empty files
    empty1 = sample_files.create_empty_file(workspace / "empty1.txt")
    empty2 = sample_files.create_empty_file(workspace / "empty2.txt")
    empty3 = sample_files.create_empty_file(workspace / "empty3.txt")

    hash1 = cli.add(empty1, root=initialized_store).stdout.strip().split()[0]
    hash2 = cli.add(empty2, root=initialized_store).stdout.strip().split()[0]
    hash3 = cli.add(empty3, root=initialized_store).stdout.strip().split()[0]

    # All should have same hash (empty content)
    assert hash1 == hash2 == hash3

    # Should only have 1 object for empty content
    # (Deduplication)


@pytest.mark.edge_case
def test_identical_directory_trees(cli, initialized_store, workspace):
    """Test that identical directory trees produce same hash."""
    # Create two identical trees
    tree1 = sample_files.create_directory_tree(workspace / "tree1", {
        "a.txt": "content a",
        "b.txt": "content b",
    })

    tree2 = sample_files.create_directory_tree(workspace / "tree2", {
        "a.txt": "content a",
        "b.txt": "content b",
    })

    hash1 = cli.add(tree1, root=initialized_store).stdout.strip().split()[0]
    hash2 = cli.add(tree2, root=initialized_store).stdout.strip().split()[0]

    # Same content = same hash
    assert hash1 == hash2


@pytest.mark.edge_case
def test_file_with_only_newlines(cli, initialized_store, workspace):
    """Test file containing only newline characters."""
    newlines_file = sample_files.create_sample_file(
        workspace / "newlines.txt",
        "\n\n\n\n\n"
    )

    result = cli.add(newlines_file, root=initialized_store)

    assert result.returncode == 0
    hash_val = result.stdout.strip().split()[0]

    # Cat should preserve newlines (cat returns bytes)
    cat_result = cli.cat(hash_val, root=initialized_store)
    assert cat_result.stdout == b"\n\n\n\n\n"


@pytest.mark.edge_case
def test_single_character_file(cli, initialized_store, workspace):
    """Test file containing single character."""
    single_char = sample_files.create_sample_file(workspace / "single.txt", "a")

    result = cli.add(single_char, root=initialized_store)
    assert result.returncode == 0

    hash_val = result.stdout.strip().split()[0]
    cat_result = cli.cat(hash_val, root=initialized_store)
    assert cat_result.stdout == b"a"


@pytest.mark.edge_case
def test_directory_with_only_subdirectories(cli, initialized_store, workspace):
    """Test directory containing only empty subdirectories."""
    tree_dir = workspace / "only_dirs"
    tree_dir.mkdir()
    (tree_dir / "subdir1").mkdir()
    (tree_dir / "subdir2").mkdir()
    (tree_dir / "subdir3").mkdir()

    result = cli.add(tree_dir, root=initialized_store)

    assert result.returncode == 0
    tree_hash = result.stdout.strip().split()[0]

    from helpers.verification import parse_tree_entries
    entries = parse_tree_entries(initialized_store, tree_hash)

    # Should have 3 tree entries (subdirectories)
    assert len(entries) == 3
    assert all(e["type"] == "tree" for e in entries)


@pytest.mark.edge_case
def test_rapid_successive_operations(cli, initialized_store, workspace):
    """Test rapid successive add/gc/refs operations."""
    files = []
    for i in range(20):
        file = sample_files.create_sample_file(workspace / f"rapid{i}.txt", f"rapid {i}")
        files.append(file)

    # Rapid adds
    hashes = []
    for file in files:
        result = cli.add(file, root=initialized_store)
        if result.returncode == 0:
            hashes.append(result.stdout.strip().split()[0])

    # Rapid ref operations
    for i, hash_val in enumerate(hashes[:10]):
        cli.refs_add(f"ref{i}", hash_val, root=initialized_store)

    # Multiple GCs
    cli.gc(root=initialized_store)
    cli.gc(root=initialized_store)
    cli.gc(root=initialized_store)

    # Should still be consistent
    remaining = count_objects(initialized_store)
    assert remaining >= 10  # At least the ref'd objects
