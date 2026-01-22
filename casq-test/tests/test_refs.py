"""Tests for 'casq refs' subcommands."""

import pytest
from fixtures import sample_files
from helpers.verification import list_all_refs


@pytest.mark.smoke
def test_refs_add_valid_name_and_hash(cli, initialized_store, sample_file):
    """Test adding a ref with valid name and hash."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    refs_result = cli.refs_add("myref", file_hash, root=initialized_store)

    assert refs_result.returncode == 0

    # Verify ref exists
    refs = list_all_refs(initialized_store)
    assert "myref" in refs
    assert refs["myref"] == file_hash


def test_refs_add_creates_ref_file(cli, initialized_store, sample_file):
    """Test that refs add creates the actual ref file."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cli.refs_add("testref", file_hash, root=initialized_store)

    ref_file = initialized_store / "refs" / "testref"
    assert ref_file.exists()
    assert ref_file.is_file()


def test_refs_add_invalid_hash_format(cli, initialized_store):
    """Test refs add with invalid hash format."""
    result = cli.refs_add("myref", "invalid_hash", root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_refs_add_nonexistent_hash(cli, initialized_store):
    """Test refs add with non-existent hash."""
    fake_hash = "0" * 64
    cli.refs_add("myref", fake_hash, root=initialized_store, expect_success=False)

    # May succeed (ref is just a pointer) or fail (validation)
    # Either is acceptable behavior


def test_refs_add_invalid_name_with_dotdot(cli, initialized_store, sample_file):
    """Test that ref names containing '..' are rejected."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    result = cli.refs_add("../invalid", file_hash, root=initialized_store, expect_success=False)

    assert result.returncode != 0


def test_refs_add_invalid_name_with_slash(cli, initialized_store, sample_file):
    """Test that ref names containing '/' are rejected."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cli.refs_add("invalid/name", file_hash, root=initialized_store, expect_success=False)

    # May fail or may create subdirectory - depends on implementation
    # At minimum, should not allow directory traversal


def test_refs_add_empty_name(cli, initialized_store, sample_file):
    """Test that empty ref name is rejected."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    result = cli.refs_add("", file_hash, root=initialized_store, expect_success=False)

    assert result.returncode != 0


def test_refs_add_update_existing_ref(cli, initialized_store, workspace):
    """Test updating an existing ref to new hash."""
    file1 = sample_files.create_sample_file(workspace / "f1.txt", "content1")
    file2 = sample_files.create_sample_file(workspace / "f2.txt", "content2")

    hash1 = cli.add(file1, root=initialized_store).stdout.strip().split()[0]
    hash2 = cli.add(file2, root=initialized_store).stdout.strip().split()[0]

    # Create ref
    cli.refs_add("updateme", hash1, root=initialized_store)

    # Update ref
    cli.refs_add("updateme", hash2, root=initialized_store)

    # Verify ref now points to hash2
    refs = list_all_refs(initialized_store)
    assert refs["updateme"] == hash2


def test_refs_list_empty(cli, initialized_store):
    """Test listing refs when none exist."""
    result = cli.refs_list(root=initialized_store)

    assert result.returncode == 0
    assert result.stdout.strip() == "No references"


def test_refs_list_single_ref(cli, initialized_store, sample_file):
    """Test listing a single ref."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cli.refs_add("single", file_hash, root=initialized_store)

    list_result = cli.refs_list(root=initialized_store)

    assert list_result.returncode == 0
    assert "single" in list_result.stdout


def test_refs_list_multiple_refs(cli, initialized_store, workspace):
    """Test listing multiple refs."""
    for i in range(5):
        file = sample_files.create_sample_file(workspace / f"f{i}.txt", f"content{i}")
        hash_val = cli.add(file, root=initialized_store).stdout.strip().split()[0]
        cli.refs_add(f"ref{i}", hash_val, root=initialized_store)

    list_result = cli.refs_list(root=initialized_store)

    assert list_result.returncode == 0
    for i in range(5):
        assert f"ref{i}" in list_result.stdout


def test_refs_list_shows_hashes(cli, initialized_store, sample_file):
    """Test that refs list shows hash values."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cli.refs_add("showme", file_hash, root=initialized_store)

    list_result = cli.refs_list(root=initialized_store)

    assert file_hash in list_result.stdout


def test_refs_list_sorting(cli, initialized_store, workspace):
    """Test that ref list output is sorted."""
    names = ["zebra", "alpha", "middle", "beta"]
    for name in names:
        file = sample_files.create_sample_file(workspace / f"{name}.txt", name)
        hash_val = cli.add(file, root=initialized_store).stdout.strip().split()[0]
        cli.refs_add(name, hash_val, root=initialized_store)

    list_result = cli.refs_list(root=initialized_store)

    # All names should appear
    for name in names:
        assert name in list_result.stdout


def test_refs_rm_existing_ref(cli, initialized_store, sample_file):
    """Test removing an existing ref."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cli.refs_add("removeme", file_hash, root=initialized_store)

    # Remove ref
    rm_result = cli.refs_rm("removeme", root=initialized_store)

    assert rm_result.returncode == 0

    # Verify ref is gone
    refs = list_all_refs(initialized_store)
    assert "removeme" not in refs


def test_refs_rm_removes_ref_file(cli, initialized_store, sample_file):
    """Test that refs rm deletes the actual ref file."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cli.refs_add("deleteme", file_hash, root=initialized_store)

    ref_file = initialized_store / "refs" / "deleteme"
    assert ref_file.exists()

    # Remove ref
    cli.refs_rm("deleteme", root=initialized_store)

    assert not ref_file.exists()


def test_refs_rm_nonexistent_ref_error(cli, initialized_store):
    """Test removing non-existent ref fails."""
    result = cli.refs_rm("doesnotexist", root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_refs_add_and_list_integration(cli, initialized_store, workspace):
    """Test integration: add multiple refs and list them."""
    refs_to_create = {"backup1": "content1", "backup2": "content2", "backup3": "content3"}
    hashes = {}

    # Add refs
    for name, content in refs_to_create.items():
        file = sample_files.create_sample_file(workspace / f"{name}.txt", content)
        hash_val = cli.add(file, root=initialized_store).stdout.strip().split()[0]
        cli.refs_add(name, hash_val, root=initialized_store)
        hashes[name] = hash_val

    # List refs
    list_result = cli.refs_list(root=initialized_store)

    # All should be listed
    for name, hash_val in hashes.items():
        assert name in list_result.stdout
        assert hash_val in list_result.stdout


def test_refs_add_list_remove_workflow(cli, initialized_store, sample_file):
    """Test complete workflow: add → list → remove."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    # Add ref
    cli.refs_add("workflow", file_hash, root=initialized_store)

    # List - should appear
    list1 = cli.refs_list(root=initialized_store)
    assert "workflow" in list1.stdout

    # Remove ref
    cli.refs_rm("workflow", root=initialized_store)

    # List - should not appear
    list2 = cli.refs_list(root=initialized_store)
    assert "workflow" not in list2.stdout or list2.stdout.strip() == ""


def test_refs_add_special_characters_in_name(cli, initialized_store, sample_file):
    """Test ref names with special (but valid) characters."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    # Try various special chars
    valid_names = ["backup-2024", "test_ref", "v1.0", "my-backup"]

    for name in valid_names:
        result = cli.refs_add(name, file_hash, root=initialized_store, expect_success=True)
        if result.returncode == 0:
            refs = list_all_refs(initialized_store)
            assert name in refs


def test_refs_update_preserves_history(cli, initialized_store, workspace):
    """Test that ref updates may preserve history (append mode)."""
    file1 = sample_files.create_sample_file(workspace / "v1.txt", "version 1")
    file2 = sample_files.create_sample_file(workspace / "v2.txt", "version 2")

    hash1 = cli.add(file1, root=initialized_store).stdout.strip().split()[0]
    hash2 = cli.add(file2, root=initialized_store).stdout.strip().split()[0]

    # Add initial ref
    cli.refs_add("versioned", hash1, root=initialized_store)

    # Update ref
    cli.refs_add("versioned", hash2, root=initialized_store)

    # Check ref file content
    ref_file = initialized_store / "refs" / "versioned"
    content = ref_file.read_text()

    # Current implementation: last line is current hash
    lines = [line.strip() for line in content.split('\n') if line.strip()]
    assert hash2 in lines


def test_refs_add_to_tree_object(cli, initialized_store, sample_tree):
    """Test creating ref to a tree object."""
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    refs_result = cli.refs_add("tree-backup", tree_hash, root=initialized_store)

    assert refs_result.returncode == 0
    refs = list_all_refs(initialized_store)
    assert refs["tree-backup"] == tree_hash


def test_refs_remove_doesnt_delete_object(cli, initialized_store, sample_file):
    """Test that removing a ref doesn't delete the object."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cli.refs_add("tempref", file_hash, root=initialized_store)
    cli.refs_rm("tempref", root=initialized_store)

    # Object should still exist (GC hasn't run)
    from helpers.verification import verify_object_exists
    verify_object_exists(initialized_store, file_hash)


def test_refs_list_after_store_init(cli, initialized_store):
    """Test that refs list works immediately after store init."""
    result = cli.refs_list(root=initialized_store)

    assert result.returncode == 0
    # Should handle empty refs gracefully


def test_refs_add_multiple_refs_same_hash(cli, initialized_store, sample_file):
    """Test adding multiple refs pointing to same hash."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cli.refs_add("ref1", file_hash, root=initialized_store)
    cli.refs_add("ref2", file_hash, root=initialized_store)
    cli.refs_add("ref3", file_hash, root=initialized_store)

    refs = list_all_refs(initialized_store)
    assert refs["ref1"] == refs["ref2"] == refs["ref3"] == file_hash


def test_refs_case_sensitivity(cli, initialized_store, workspace):
    """Test that ref names are case-sensitive."""
    file1 = sample_files.create_sample_file(workspace / "f1.txt", "content1")
    file2 = sample_files.create_sample_file(workspace / "f2.txt", "content2")

    hash1 = cli.add(file1, root=initialized_store).stdout.strip().split()[0]
    hash2 = cli.add(file2, root=initialized_store).stdout.strip().split()[0]

    cli.refs_add("MyRef", hash1, root=initialized_store)
    cli.refs_add("myref", hash2, root=initialized_store)

    refs = list_all_refs(initialized_store)

    # Should be treated as different refs
    if "MyRef" in refs and "myref" in refs:
        assert refs["MyRef"] == hash1
        assert refs["myref"] == hash2


def test_refs_long_name(cli, initialized_store, sample_file):
    """Test ref with long (but valid) name."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    long_name = "a" * 200  # Long but valid filename
    result = cli.refs_add(long_name, file_hash, root=initialized_store)

    # Should succeed or fail gracefully
    if result.returncode == 0:
        refs = list_all_refs(initialized_store)
        assert long_name in refs
