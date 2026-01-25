"""Tests for 'casq orphans' command."""

import pytest
from fixtures import sample_files
from helpers.verification import (
    verify_object_exists,
    get_object_type,
    count_objects,
)


@pytest.mark.smoke
def test_orphans_empty_store(cli, initialized_store):
    """Test orphans command on empty store."""
    result = cli.orphans(root=initialized_store)

    assert result.returncode == 0
    assert "No orphaned objects found" in result.stderr


@pytest.mark.smoke
def test_orphans_with_single_blob(cli, initialized_store, sample_file):
    """Test that orphaned blobs ARE shown."""
    # Add file without ref - creates orphaned blob
    add_result = cli.add(sample_file, root=initialized_store)
    hash_output = add_result.stderr.strip().split()[0]

    # Verify it's a blob
    assert get_object_type(initialized_store, hash_output) == "blob"

    # Blob should be listed as orphan
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0
    assert hash_output in result.stderr
    assert "blob" in result.stderr


@pytest.mark.smoke
def test_orphans_with_single_tree(cli, initialized_store, sample_tree):
    """Test that orphaned tree is shown."""
    # Add tree without ref - creates orphaned tree
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stderr.strip().split()[0]

    # Verify it's a tree
    assert get_object_type(initialized_store, tree_hash) == "tree"

    # Tree should be listed as orphan
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0
    assert tree_hash in result.stderr


def test_orphans_mixed_blobs_and_trees(cli, initialized_store, workspace, sample_file):
    """Test that both orphaned blobs and trees are shown."""
    # Create orphaned blob
    blob_hash = cli.add(sample_file, root=initialized_store).stderr.strip().split()[0]

    # Create orphaned tree
    tree = sample_files.create_directory_tree(
        workspace / "tree", {"file.txt": "tree content"}
    )
    tree_hash = cli.add(tree, root=initialized_store).stderr.strip().split()[0]

    # Both should be listed
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0
    assert blob_hash in result.stderr
    assert tree_hash in result.stderr
    assert "blob" in result.stderr
    assert "tree" in result.stderr


def test_orphans_with_referenced_tree(cli, initialized_store, sample_tree):
    """Test that referenced trees are NOT shown as orphans."""
    # Add tree with ref
    add_result = cli.add(sample_tree, root=initialized_store, ref_name="backup")
    tree_hash = add_result.stderr.strip().split()[0]

    verify_object_exists(initialized_store, tree_hash)

    # Should have no orphans
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0
    assert "No orphaned objects found" in result.stderr


def test_orphans_multiple_orphaned_trees(cli, initialized_store, workspace):
    """Test multiple orphaned trees are all listed."""
    # Create multiple trees
    tree1 = sample_files.create_directory_tree(
        workspace / "tree1", {"file1.txt": "content1"}
    )
    tree2 = sample_files.create_directory_tree(
        workspace / "tree2", {"file2.txt": "content2"}
    )
    tree3 = sample_files.create_directory_tree(
        workspace / "tree3", {"file3.txt": "content3"}
    )

    # Add all without refs
    hash1 = cli.add(tree1, root=initialized_store).stderr.strip().split()[0]
    hash2 = cli.add(tree2, root=initialized_store).stderr.strip().split()[0]
    hash3 = cli.add(tree3, root=initialized_store).stderr.strip().split()[0]

    # All should be listed as orphans
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0

    output = result.stderr
    assert hash1 in output
    assert hash2 in output
    assert hash3 in output


def test_orphans_mixed_referenced_and_orphaned(cli, initialized_store, workspace):
    """Test mixed scenario with both referenced and orphaned trees."""
    # Create trees
    tree1 = sample_files.create_directory_tree(
        workspace / "tree1", {"file1.txt": "content1"}
    )
    tree2 = sample_files.create_directory_tree(
        workspace / "tree2", {"file2.txt": "content2"}
    )

    # Add tree1 with ref, tree2 without
    hash1 = (
        cli.add(tree1, root=initialized_store, ref_name="backup")
        .stderr.strip()
        .split()[0]
    )
    hash2 = cli.add(tree2, root=initialized_store).stderr.strip().split()[0]

    # Only tree2 should be orphan
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0

    output = result.stderr
    assert hash1 not in output  # Referenced, not orphan
    assert hash2 in output  # Orphaned


def test_orphans_after_ref_deletion(cli, initialized_store, sample_tree):
    """Test that tree becomes orphan after its ref is deleted."""
    # Add tree with ref
    add_result = cli.add(sample_tree, root=initialized_store, ref_name="temp")
    tree_hash = add_result.stderr.strip().split()[0]

    # Initially no orphans
    result1 = cli.orphans(root=initialized_store)
    assert result1.returncode == 0
    assert tree_hash not in result1.stderr

    # Delete ref
    cli.refs_rm("temp", root=initialized_store)

    # Now should be orphan
    result2 = cli.orphans(root=initialized_store)
    assert result2.returncode == 0
    assert tree_hash in result2.stderr


def test_orphans_nested_trees_only_show_root(cli, initialized_store, nested_tree):
    """Test that only top-level orphan roots are shown, not child trees."""
    # Add nested tree without ref - creates orphaned tree with child trees
    add_result = cli.add(nested_tree, root=initialized_store)
    root_hash = add_result.stderr.strip().split()[0]

    # Only the root tree should be listed
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0

    output_lines = [line for line in result.stderr.strip().split("\n") if line]

    # Should contain the root hash
    assert any(root_hash in line for line in output_lines)


def test_orphans_long_format(cli, initialized_store, sample_tree):
    """Test orphans command with --long flag."""
    # Add orphaned tree
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stderr.strip().split()[0]

    # Use long format
    result = cli.orphans(root=initialized_store, long_format=True)
    assert result.returncode == 0

    output = result.stderr

    # Long format should include hash
    assert tree_hash in output

    # Long format should have more details (multiple lines per orphan)
    # The exact format may vary, but it should be longer than short format
    short_result = cli.orphans(root=initialized_store, long_format=False)
    assert len(output) > len(short_result.stderr)


def test_orphans_long_format_shows_metadata(cli, initialized_store, sample_tree):
    """Test that long format includes entry count and size information."""
    # Add orphaned tree
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stderr.strip().split()[0]

    # Use long format
    result = cli.orphans(root=initialized_store, long_format=True)
    assert result.returncode == 0

    # Should contain metadata keywords
    assert tree_hash in result.stderr
    assert "Type: tree" in result.stderr
    assert "Entries:" in result.stderr
    assert "Approx size:" in result.stderr


def test_orphans_long_format_blob_no_entry_count(cli, initialized_store, sample_file):
    """Test that long format for blobs does not include entry count."""
    # Add orphaned blob
    add_result = cli.add(sample_file, root=initialized_store)
    blob_hash = add_result.stderr.strip().split()[0]

    # Use long format
    result = cli.orphans(root=initialized_store, long_format=True)
    assert result.returncode == 0

    # Should contain blob metadata but NOT entry count
    assert blob_hash in result.stderr
    assert "Type: blob" in result.stderr
    assert "Approx size:" in result.stderr

    # Split output into sections by "---"
    sections = result.stderr.split("---")
    blob_section = None
    for section in sections:
        if blob_hash in section:
            blob_section = section
            break

    # Blob section should not have "Entries:"
    assert blob_section is not None
    assert "Entries:" not in blob_section


def test_orphans_after_gc(cli, initialized_store, sample_tree):
    """Test that orphans command works after GC removes orphans."""
    # Add orphaned tree
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stderr.strip().split()[0]

    # Verify it's an orphan
    result1 = cli.orphans(root=initialized_store)
    assert tree_hash in result1.stderr

    # Run GC to delete orphans
    cli.gc(root=initialized_store)

    # Orphans should now be empty
    result2 = cli.orphans(root=initialized_store)
    assert result2.returncode == 0
    assert "No orphaned objects found" in result2.stderr


def test_orphans_complex_tree(cli, initialized_store, complex_tree):
    """Test orphans command with complex tree structure."""
    # Add complex tree without ref
    add_result = cli.add(complex_tree, root=initialized_store)
    tree_hash = add_result.stderr.strip().split()[0]

    # Should be listed as orphan
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0
    assert tree_hash in result.stderr


def test_orphans_multiple_refs_to_same_tree(cli, initialized_store, sample_tree):
    """Test that tree with multiple refs is not orphaned."""
    # Add tree with one ref
    add_result = cli.add(sample_tree, root=initialized_store, ref_name="ref1")
    tree_hash = add_result.stderr.strip().split()[0]

    # Add another ref to same tree
    cli.refs_add("ref2", tree_hash, root=initialized_store)

    # Should not be orphan
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0
    assert tree_hash not in result.stderr

    # Remove one ref
    cli.refs_rm("ref1", root=initialized_store)

    # Still should not be orphan (ref2 exists)
    result2 = cli.orphans(root=initialized_store)
    assert result2.returncode == 0
    assert tree_hash not in result2.stderr

    # Remove last ref
    cli.refs_rm("ref2", root=initialized_store)

    # Now should be orphan
    result3 = cli.orphans(root=initialized_store)
    assert result3.returncode == 0
    assert tree_hash in result3.stderr


def test_orphans_preserves_object_integrity(cli, initialized_store, sample_tree):
    """Test that orphans command doesn't modify store."""
    # Add orphaned tree
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stderr.strip().split()[0]

    # Count objects before
    count_before = count_objects(initialized_store)

    # Run orphans command
    cli.orphans(root=initialized_store)

    # Count objects after
    count_after = count_objects(initialized_store)

    # Should be unchanged
    assert count_before == count_after
    verify_object_exists(initialized_store, tree_hash)


def test_orphans_with_empty_refs_directory(cli, initialized_store, sample_tree):
    """Test orphans when refs directory exists but is empty."""
    # Add tree without ref
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stderr.strip().split()[0]

    # Ensure refs dir is empty
    refs_dir = initialized_store / "refs"
    for ref_file in refs_dir.iterdir():
        ref_file.unlink()

    # Should list the tree as orphan
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0
    assert tree_hash in result.stderr


def test_orphans_large_number_of_orphans(cli, initialized_store, workspace):
    """Test orphans command with many orphaned trees."""
    # Create many orphaned trees
    orphan_hashes = []
    for i in range(20):
        tree = sample_files.create_directory_tree(
            workspace / f"tree{i}", {f"file{i}.txt": f"content{i}"}
        )
        hash_val = cli.add(tree, root=initialized_store).stderr.strip().split()[0]
        orphan_hashes.append(hash_val)

    # All should be listed
    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0

    for hash_val in orphan_hashes:
        assert hash_val in result.stderr


def test_orphans_output_format_consistency(cli, initialized_store, sample_tree):
    """Test that orphans output format is consistent."""
    # Add orphaned tree
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stderr.strip().split()[0]

    # Run orphans multiple times
    result1 = cli.orphans(root=initialized_store)
    result2 = cli.orphans(root=initialized_store)

    # Output should be identical
    assert result1.stderr == result2.stderr
    assert tree_hash in result1.stderr
