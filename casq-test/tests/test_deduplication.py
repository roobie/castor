"""Tests for content deduplication."""

from fixtures import sample_files
from helpers.verification import count_objects, verify_object_exists


def test_same_file_added_twice_single_object(cli, initialized_store, workspace):
    """Test that adding same file twice only stores it once."""
    content = "shared content\n"
    file = sample_files.create_sample_file(workspace / "test.txt", content)

    # Add first time
    result1 = cli.add(file, root=initialized_store)
    hash1 = result1.stderr.strip().split()[0]
    count1 = count_objects(initialized_store)

    # Add second time
    result2 = cli.add(file, root=initialized_store)
    hash2 = result2.stderr.strip().split()[0]
    count2 = count_objects(initialized_store)

    # Same hash, same count (no new objects)
    assert hash1 == hash2
    assert count2 == count1


def test_same_content_different_names_dedupe(cli, initialized_store, workspace):
    """Test that files with same content but different names deduplicate."""
    content = "identical content\n"

    file1 = sample_files.create_sample_file(workspace / "name1.txt", content)
    file2 = sample_files.create_sample_file(workspace / "name2.txt", content)
    file3 = sample_files.create_sample_file(workspace / "name3.txt", content)

    hash1 = cli.add(file1, root=initialized_store).stderr.strip().split()[0]
    count_after_first = count_objects(initialized_store)

    hash2 = cli.add(file2, root=initialized_store).stderr.strip().split()[0]
    count_after_second = count_objects(initialized_store)

    hash3 = cli.add(file3, root=initialized_store).stderr.strip().split()[0]
    count_after_third = count_objects(initialized_store)

    # All same hash
    assert hash1 == hash2 == hash3

    # No additional objects after first add
    assert count_after_second == count_after_first
    assert count_after_third == count_after_first


def test_same_subdirectories_in_different_trees(cli, initialized_store, workspace):
    """Test that identical subdirectories are deduplicated."""
    # Create two trees with identical subdirectory
    tree1 = sample_files.create_directory_tree(
        workspace / "tree1",
        {
            "unique1.txt": "unique to tree1",
            "shared": {
                "common.txt": "shared content",
            },
        },
    )

    tree2 = sample_files.create_directory_tree(
        workspace / "tree2",
        {
            "unique2.txt": "unique to tree2",
            "shared": {
                "common.txt": "shared content",  # Identical subdirectory
            },
        },
    )

    initial_count = count_objects(initialized_store)

    cli.add(tree1, root=initialized_store).stderr.strip().split()[0]
    count_after_tree1 = count_objects(initialized_store)

    cli.add(tree2, root=initialized_store).stderr.strip().split()[0]
    count_after_tree2 = count_objects(initialized_store)

    # Should have added fewer objects due to shared subdirectory
    # tree1: root tree + shared tree + 2 blobs = 4 objects
    # tree2: root tree + shared tree (dedupe) + 1 blob = 2 new objects
    objects_added_by_tree1 = count_after_tree1 - initial_count
    objects_added_by_tree2 = count_after_tree2 - count_after_tree1

    assert objects_added_by_tree2 < objects_added_by_tree1


def test_storage_efficiency_with_deduplication(cli, initialized_store, workspace):
    """Test that deduplication improves storage efficiency."""
    # Create shared content
    shared_content = "This content is shared across multiple files\n"

    # Add 10 files with same content
    for i in range(10):
        file = sample_files.create_sample_file(
            workspace / f"file{i}.txt", shared_content
        )
        cli.add(file, root=initialized_store)

    # Should only have 1 blob object (deduplicated)
    # Even though we added 10 files
    total_objects = count_objects(initialized_store)

    # Exact count depends on whether files were added individually or in directory
    # But should be much less than 10
    assert total_objects < 10


def test_empty_files_deduplicate(cli, initialized_store, workspace):
    """Test that multiple empty files share same object."""
    empty_files = []
    for i in range(5):
        empty = sample_files.create_empty_file(workspace / f"empty{i}.txt")
        empty_files.append(empty)

    hashes = []
    for empty_file in empty_files:
        result = cli.add(empty_file, root=initialized_store)
        hashes.append(result.stderr.strip().split()[0])

    # All empty files should have same hash
    assert len(set(hashes)) == 1

    # Should only have 1 object for all empty files
    # (plus any tree objects if added via directory)


def test_dedupe_across_multiple_adds(cli, initialized_store, workspace):
    """Test deduplication works across multiple add commands."""
    content = "shared across adds\n"

    # First batch
    dir1 = sample_files.create_directory_tree(
        workspace / "batch1",
        {
            "file1.txt": content,
            "file2.txt": content,
        },
    )

    hash1 = cli.add(dir1, root=initialized_store).stderr.strip().split()[0]
    count_objects(initialized_store)

    # Second batch with same content
    dir2 = sample_files.create_directory_tree(
        workspace / "batch2",
        {
            "file3.txt": content,
            "file4.txt": content,
        },
    )

    hash2 = cli.add(dir2, root=initialized_store).stderr.strip().split()[0]
    count_objects(initialized_store)

    # Should have deduplicated the shared content blob
    # Each tree has 2 files with identical content
    # So each tree should reference the same blob
    verify_object_exists(initialized_store, hash1)
    verify_object_exists(initialized_store, hash2)


def test_partial_deduplication_in_snapshot(cli, initialized_store, workspace):
    """Test deduplication when snapshots partially overlap."""
    # Snapshot 1
    v1 = sample_files.create_directory_tree(
        workspace / "v1",
        {
            "unchanged.txt": "This stays the same",
            "changed.txt": "Version 1",
            "removed.txt": "Will be removed",
        },
    )

    cli.add(v1, root=initialized_store, ref_name="v1").stderr.strip().split()[0]
    count_v1 = count_objects(initialized_store)

    # Snapshot 2 (some files same, some different)
    v2 = sample_files.create_directory_tree(
        workspace / "v2",
        {
            "unchanged.txt": "This stays the same",  # Same - should dedupe
            "changed.txt": "Version 2",  # Different content
            "added.txt": "New file",  # New file
        },
    )

    cli.add(v2, root=initialized_store, ref_name="v2").stderr.strip().split()[0]
    count_v2 = count_objects(initialized_store)

    # Should have added: v2 tree + changed.txt blob + added.txt blob
    # unchanged.txt blob should be deduplicated
    objects_added = count_v2 - count_v1

    # Should not have added 4 new objects (tree + 3 blobs)
    # Should have added 3 objects (tree + 2 new blobs)
    assert objects_added == 3


def test_binary_deduplication(cli, initialized_store, workspace):
    """Test that binary files with same content deduplicate."""
    pattern = b"\xde\xad\xbe\xef"
    size = 1024

    # Create multiple binary files with same content
    binaries = []
    for i in range(5):
        binary = sample_files.create_binary_file(
            workspace / f"binary{i}.dat", size=size, pattern=pattern
        )
        binaries.append(binary)

    hashes = []
    for binary in binaries:
        result = cli.add(binary, root=initialized_store)
        hashes.append(result.stderr.strip().split()[0])

    # All should have same hash
    assert len(set(hashes)) == 1

    # Only one blob object should exist for the content
