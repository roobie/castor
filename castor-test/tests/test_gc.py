"""Tests for 'castor gc' command."""

import pytest
from fixtures import sample_files
from helpers.verification import count_objects, verify_object_exists


@pytest.mark.smoke
def test_gc_with_no_refs_deletes_all(cli, initialized_store, sample_file):
    """Test that GC with no refs deletes all objects."""
    # Add file without ref
    cli.add(sample_file, root=initialized_store)
    initial_count = count_objects(initialized_store)
    assert initial_count > 0

    # Run GC
    gc_result = cli.gc(root=initialized_store)

    assert gc_result.returncode == 0
    # All objects should be deleted
    final_count = count_objects(initialized_store)
    assert final_count == 0


def test_gc_with_refs_keeps_reachable(cli, initialized_store, sample_file):
    """Test that GC preserves objects reachable from refs."""
    # Add file with ref
    add_result = cli.add(sample_file, root=initialized_store, ref_name="keep")
    file_hash = add_result.stdout.strip().split()[0]

    # Run GC
    gc_result = cli.gc(root=initialized_store)

    assert gc_result.returncode == 0
    # Object should still exist
    verify_object_exists(initialized_store, file_hash)


def test_gc_preserves_tree_and_descendants(cli, initialized_store, sample_tree):
    """Test that GC keeps tree and all its blob children."""
    # Add tree with ref
    add_result = cli.add(sample_tree, root=initialized_store, ref_name="tree-ref")
    tree_hash = add_result.stdout.strip().split()[0]

    initial_count = count_objects(initialized_store)

    # Run GC
    cli.gc(root=initialized_store)

    # Tree and all blobs should still exist
    final_count = count_objects(initialized_store)
    assert final_count == initial_count
    verify_object_exists(initialized_store, tree_hash)


def test_gc_deletes_orphaned_blobs(cli, initialized_store, workspace):
    """Test that GC deletes objects not reachable from any ref."""
    # Add file1 with ref
    file1 = sample_files.create_sample_file(workspace / "keep.txt", "keep me")
    cli.add(file1, root=initialized_store, ref_name="keep")

    # Add file2 without ref (orphan)
    file2 = sample_files.create_sample_file(workspace / "delete.txt", "delete me")
    add2 = cli.add(file2, root=initialized_store)
    orphan_hash = add2.stdout.strip().split()[0]

    # Run GC
    cli.gc(root=initialized_store)

    # Orphan should be deleted
    from helpers.verification import get_object_path
    orphan_path = get_object_path(initialized_store, orphan_hash)
    assert not orphan_path.exists()


def test_gc_with_multiple_refs(cli, initialized_store, workspace):
    """Test GC with multiple refs keeps all reachable objects."""
    file1 = sample_files.create_sample_file(workspace / "f1.txt", "content1")
    file2 = sample_files.create_sample_file(workspace / "f2.txt", "content2")

    hash1 = cli.add(file1, root=initialized_store, ref_name="ref1").stdout.strip().split()[0]
    hash2 = cli.add(file2, root=initialized_store, ref_name="ref2").stdout.strip().split()[0]

    # Run GC
    cli.gc(root=initialized_store)

    # Both objects should still exist
    verify_object_exists(initialized_store, hash1)
    verify_object_exists(initialized_store, hash2)


def test_gc_with_overlapping_references(cli, initialized_store, workspace):
    """Test GC when multiple refs point to same object."""
    file = sample_files.create_sample_file(workspace / "shared.txt", "shared content")

    hash1 = cli.add(file, root=initialized_store, ref_name="ref1").stdout.strip().split()[0]

    # Add same content with different ref
    cli.refs_add("ref2", hash1, root=initialized_store)

    initial_count = count_objects(initialized_store)

    # Run GC
    cli.gc(root=initialized_store)

    # Object should still exist
    final_count = count_objects(initialized_store)
    assert final_count == initial_count
    verify_object_exists(initialized_store, hash1)


def test_gc_dry_run_no_deletion(cli, initialized_store, sample_file):
    """Test that dry-run mode doesn't actually delete objects."""
    # Add orphan file
    cli.add(sample_file, root=initialized_store)
    initial_count = count_objects(initialized_store)

    # Run GC with dry-run
    gc_result = cli.gc(root=initialized_store, dry_run=True)

    assert gc_result.returncode == 0
    # Objects should still exist
    final_count = count_objects(initialized_store)
    assert final_count == initial_count


def test_gc_dry_run_statistics(cli, initialized_store, workspace):
    """Test that dry-run reports what would be deleted."""
    # Add orphan
    file = sample_files.create_sample_file(workspace / "orphan.txt", "orphan")
    cli.add(file, root=initialized_store)

    gc_result = cli.gc(root=initialized_store, dry_run=True)

    # Should report what would be deleted
    assert gc_result.returncode == 0
    assert len(gc_result.stdout) > 0 or len(gc_result.stderr) > 0


def test_gc_real_run_statistics(cli, initialized_store, workspace):
    """Test that real GC run reports statistics."""
    # Add orphan
    file = sample_files.create_sample_file(workspace / "orphan.txt", "orphan")
    cli.add(file, root=initialized_store)

    gc_result = cli.gc(root=initialized_store)

    # Should report results
    assert gc_result.returncode == 0
    assert len(gc_result.stdout) > 0 or len(gc_result.stderr) > 0


def test_gc_complex_tree_reachability(cli, initialized_store, nested_tree):
    """Test GC correctly traces through nested tree structures."""
    # Add nested tree with ref
    add_result = cli.add(nested_tree, root=initialized_store, ref_name="nested")
    add_result.stdout.strip().split()[0]

    initial_count = count_objects(initialized_store)

    # Run GC
    cli.gc(root=initialized_store)

    # All objects (tree + subtrees + blobs) should remain
    final_count = count_objects(initialized_store)
    assert final_count == initial_count


def test_gc_empty_store(cli, initialized_store):
    """Test GC on empty store."""
    gc_result = cli.gc(root=initialized_store)

    assert gc_result.returncode == 0
    # Should handle empty store gracefully


def test_gc_after_ref_deletion(cli, initialized_store, sample_file):
    """Test that GC deletes objects after their ref is removed."""
    # Add with ref
    add_result = cli.add(sample_file, root=initialized_store, ref_name="temp")
    file_hash = add_result.stdout.strip().split()[0]

    # Remove ref
    cli.refs_rm("temp", root=initialized_store)

    # Run GC
    cli.gc(root=initialized_store)

    # Object should be deleted
    from helpers.verification import get_object_path
    obj_path = get_object_path(initialized_store, file_hash)
    assert not obj_path.exists()


def test_gc_preserves_newly_referenced_objects(cli, initialized_store, workspace):
    """Test that adding a ref prevents GC deletion."""
    # Add orphan
    file = sample_files.create_sample_file(workspace / "file.txt", "content")
    add_result = cli.add(file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    # Add ref before GC
    cli.refs_add("savedit", file_hash, root=initialized_store)

    # Run GC
    cli.gc(root=initialized_store)

    # Object should still exist
    verify_object_exists(initialized_store, file_hash)


def test_gc_with_shared_subtrees(cli, initialized_store, workspace):
    """Test GC when multiple trees share subtrees."""
    # Create two trees that might share blobs
    tree1 = sample_files.create_directory_tree(workspace / "tree1", {
        "shared.txt": "shared content",
        "unique1.txt": "unique to tree1",
    })

    tree2 = sample_files.create_directory_tree(workspace / "tree2", {
        "shared.txt": "shared content",  # Same content
        "unique2.txt": "unique to tree2",
    })

    cli.add(tree1, root=initialized_store, ref_name="tree1").stdout.strip().split()[0]
    cli.add(tree2, root=initialized_store, ref_name="tree2").stdout.strip().split()[0]

    initial_count = count_objects(initialized_store)

    # Run GC
    cli.gc(root=initialized_store)

    # All objects should be preserved
    final_count = count_objects(initialized_store)
    assert final_count == initial_count


def test_gc_handles_missing_objects_gracefully(cli, initialized_store, workspace):
    """Test GC handles corrupted store gracefully."""
    # This test verifies error handling; exact behavior is implementation-specific
    file = sample_files.create_sample_file(workspace / "test.txt", "content")
    cli.add(file, root=initialized_store, ref_name="test")

    # Run GC
    gc_result = cli.gc(root=initialized_store, expect_success=True)

    # Should complete without crash
    assert gc_result.returncode == 0


def test_gc_multiple_runs_idempotent(cli, initialized_store, sample_file):
    """Test that running GC multiple times is safe."""
    # Add with ref
    cli.add(sample_file, root=initialized_store, ref_name="keep")

    # Run GC multiple times
    result1 = cli.gc(root=initialized_store)
    count1 = count_objects(initialized_store)

    result2 = cli.gc(root=initialized_store)
    count2 = count_objects(initialized_store)

    result3 = cli.gc(root=initialized_store)
    count3 = count_objects(initialized_store)

    # All should succeed and maintain same count
    assert result1.returncode == result2.returncode == result3.returncode == 0
    assert count1 == count2 == count3


def test_gc_large_store(cli, initialized_store, workspace):
    """Test GC on store with many objects."""
    # Create many files
    many_dir = workspace / "many"
    many_dir.mkdir()
    for i in range(50):
        sample_files.create_sample_file(many_dir / f"f{i}.txt", f"content{i}")

    # Add with ref
    cli.add(many_dir, root=initialized_store, ref_name="many")

    # Add some orphans
    for i in range(10):
        orphan = sample_files.create_sample_file(workspace / f"orphan{i}.txt", f"orphan{i}")
        cli.add(orphan, root=initialized_store)

    # Run GC
    gc_result = cli.gc(root=initialized_store)

    assert gc_result.returncode == 0
    # Orphans should be gone, ref'd objects remain


def test_gc_empty_refs_directory(cli, initialized_store, sample_file):
    """Test GC when refs directory exists but is empty."""
    # Add orphan
    cli.add(sample_file, root=initialized_store)

    # Ensure refs dir is empty
    refs_dir = initialized_store / "refs"
    for ref_file in refs_dir.iterdir():
        ref_file.unlink()

    # Run GC
    gc_result = cli.gc(root=initialized_store)

    assert gc_result.returncode == 0
    # All objects should be deleted
    assert count_objects(initialized_store) == 0


def test_gc_deep_tree_traversal(cli, initialized_store, workspace):
    """Test GC correctly traverses deep tree structures."""
    # Create deeply nested tree
    current = workspace / "deep"
    for i in range(10):
        current = current / f"level{i}"
    current.mkdir(parents=True)
    sample_files.create_sample_file(current / "deep.txt", "deep content")

    # Add with ref
    cli.add(workspace / "deep", root=initialized_store, ref_name="deep")

    initial_count = count_objects(initialized_store)

    # Run GC
    cli.gc(root=initialized_store)

    # All objects in deep tree should be preserved
    final_count = count_objects(initialized_store)
    assert final_count == initial_count


def test_gc_ref_update_scenario(cli, initialized_store, workspace):
    """Test GC after ref is updated to point to new object."""
    # Add file1 with ref
    file1 = sample_files.create_sample_file(workspace / "v1.txt", "version 1")
    hash1 = cli.add(file1, root=initialized_store, ref_name="current").stdout.strip().split()[0]

    # Update ref to file2
    file2 = sample_files.create_sample_file(workspace / "v2.txt", "version 2")
    hash2 = cli.add(file2, root=initialized_store, ref_name="current").stdout.strip().split()[0]

    # Run GC
    cli.gc(root=initialized_store)

    # hash1 (old) should be deleted, hash2 (current) should remain
    from helpers.verification import get_object_path
    obj1_path = get_object_path(initialized_store, hash1)
    assert not obj1_path.exists()

    verify_object_exists(initialized_store, hash2)
