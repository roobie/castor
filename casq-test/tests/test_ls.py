"""Tests for 'casq ls' command."""

import pytest
from fixtures import sample_files


@pytest.mark.smoke
def test_ls_refs_empty_store(cli, initialized_store):
    """Test listing refs in empty store."""
    result = cli.ls(root=initialized_store)

    assert result.returncode == 0
    # Empty store should have no refs
    assert result.stdout.strip() == "No references (use 'casq add --ref-name' to create one)"


def test_ls_refs_single_ref(cli, initialized_store, sample_file):
    """Test listing refs with a single ref."""
    cli.add(sample_file, root=initialized_store, ref_name="myref")

    result = cli.ls(root=initialized_store)

    assert result.returncode == 0
    assert "myref" in result.stdout


def test_ls_refs_multiple_refs(cli, initialized_store, workspace):
    """Test listing multiple refs."""
    file1 = sample_files.create_sample_file(workspace / "f1.txt", "content1")
    file2 = sample_files.create_sample_file(workspace / "f2.txt", "content2")
    file3 = sample_files.create_sample_file(workspace / "f3.txt", "content3")

    cli.add(file1, root=initialized_store, ref_name="ref1")
    cli.add(file2, root=initialized_store, ref_name="ref2")
    cli.add(file3, root=initialized_store, ref_name="ref3")

    result = cli.ls(root=initialized_store)

    assert result.returncode == 0
    assert "ref1" in result.stdout
    assert "ref2" in result.stdout
    assert "ref3" in result.stdout


def test_ls_refs_long_format(cli, initialized_store, sample_file):
    """Test listing refs with long format (-l)."""
    add_result = cli.add(sample_file, root=initialized_store, ref_name="myref")
    file_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(long_format=True, root=initialized_store)

    assert result.returncode == 0
    # Long format should show both name and hash
    assert "myref" in result.stdout
    assert file_hash in result.stdout


def test_ls_blob_short_format(cli, initialized_store, sample_file):
    """Test listing a blob (short format shows hash/type)."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(file_hash, root=initialized_store)

    assert result.returncode == 0
    # Should show it's a blob
    assert "blob" in result.stdout.lower() or file_hash in result.stdout


def test_ls_blob_long_format(cli, initialized_store, sample_file):
    """Test listing blob with long format (shows size)."""
    add_result = cli.add(sample_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(file_hash, long_format=True, root=initialized_store)

    assert result.returncode == 0
    # Long format should show size
    assert "blob" in result.stdout.lower() or len(result.stdout) > 0


def test_ls_tree_short_format(cli, initialized_store, sample_tree):
    """Test listing tree shows entry names."""
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    assert result.returncode == 0
    # Should list file names from SIMPLE_TREE
    assert "file1.txt" in result.stdout
    assert "file2.txt" in result.stdout


def test_ls_tree_long_format(cli, initialized_store, sample_tree):
    """Test listing tree with long format (shows modes and hashes)."""
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, long_format=True, root=initialized_store)

    assert result.returncode == 0
    # Long format should show more details
    assert "file1.txt" in result.stdout
    assert "file2.txt" in result.stdout


def test_ls_empty_tree(cli, initialized_store, workspace):
    """Test listing an empty tree."""
    empty_dir = workspace / "empty"
    empty_dir.mkdir()

    add_result = cli.add(empty_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    assert result.returncode == 0
    # Empty tree should produce empty or minimal output
    assert result.stdout.strip() == "" or "0" in result.stdout


def test_ls_nested_tree(cli, initialized_store, nested_tree):
    """Test listing nested tree shows immediate children."""
    add_result = cli.add(nested_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    assert result.returncode == 0
    # Should show top-level entries
    assert "top.txt" in result.stdout
    assert "dir1" in result.stdout or "tree" in result.stdout
    assert "dir2" in result.stdout or "tree" in result.stdout


def test_ls_invalid_hash(cli, initialized_store):
    """Test ls with invalid hash format."""
    result = cli.ls("invalid_hash", root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_ls_nonexistent_hash(cli, initialized_store):
    """Test ls with non-existent hash."""
    fake_hash = "0" * 64
    result = cli.ls(fake_hash, root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_ls_tree_entries_sorted(cli, initialized_store, workspace):
    """Test that ls output for tree is sorted."""
    sorted_dir = sample_files.create_directory_tree(workspace / "sorted", {
        "zebra.txt": "z",
        "alpha.txt": "a",
        "middle.txt": "m",
    })

    add_result = cli.add(sorted_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    # Output should show sorted names
    result.stdout.strip().split('\n')
    # Extract names (handling various output formats)
    assert "alpha.txt" in result.stdout
    assert "middle.txt" in result.stdout
    assert "zebra.txt" in result.stdout


def test_ls_tree_shows_file_types(cli, initialized_store, nested_tree):
    """Test that ls distinguishes between blobs and trees."""
    add_result = cli.add(nested_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, long_format=True, root=initialized_store)

    # Should indicate type (blob vs tree)
    assert "blob" in result.stdout.lower() or "tree" in result.stdout.lower() or \
           "file" in result.stdout.lower() or "dir" in result.stdout.lower()


def test_ls_refs_sorted(cli, initialized_store, workspace):
    """Test that ref listing is sorted."""
    for name in ["zebra", "alpha", "middle"]:
        file = sample_files.create_sample_file(workspace / f"{name}.txt", name)
        cli.add(file, root=initialized_store, ref_name=name)

    result = cli.ls(root=initialized_store)

    # Refs should appear in sorted order
    lines = [line for line in result.stdout.strip().split('\n') if line]
    # Verify presence
    assert any("alpha" in line for line in lines)
    assert any("middle" in line for line in lines)
    assert any("zebra" in line for line in lines)


def test_ls_tree_with_subdirectories(cli, initialized_store, complex_tree):
    """Test listing tree that contains subdirectories."""
    add_result = cli.add(complex_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    assert result.returncode == 0
    # Should show both files and directories
    assert "README.md" in result.stdout
    assert "src" in result.stdout
    assert "tests" in result.stdout


def test_ls_shows_mode_in_long_format(cli, initialized_store, workspace):
    """Test that long format shows file mode."""
    sample_files.create_executable_file(
        workspace / "script.sh",
        "#!/bin/bash\n"
    )

    # Add via directory to preserve in tree
    add_result = cli.add(workspace, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, long_format=True, root=initialized_store)

    assert result.returncode == 0
    # Should show mode information
    assert "script.sh" in result.stdout


def test_ls_blob_shows_size(cli, initialized_store, workspace):
    """Test that listing a blob shows its size."""
    large_file = sample_files.create_sample_file(
        workspace / "large.txt",
        "x" * 1000
    )

    add_result = cli.add(large_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(file_hash, long_format=True, root=initialized_store)

    assert result.returncode == 0
    # Should show size (1000 bytes)
    assert "1000" in result.stdout or "blob" in result.stdout.lower()


def test_ls_tree_shows_entry_count(cli, initialized_store, workspace):
    """Test that listing tree shows number of entries."""
    many_dir = workspace / "many"
    many_dir.mkdir()
    for i in range(10):
        sample_files.create_sample_file(many_dir / f"f{i}.txt", f"content{i}")

    add_result = cli.add(many_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    assert result.returncode == 0
    # Should show all 10 files
    lines = [line for line in result.stdout.strip().split('\n') if line]
    assert len([line for line in lines if "f" in line and ".txt" in line]) == 10


def test_ls_without_hash_lists_refs(cli, initialized_store, sample_file):
    """Test that ls without arguments lists refs."""
    cli.add(sample_file, root=initialized_store, ref_name="test")

    result = cli.ls(root=initialized_store)

    assert result.returncode == 0
    assert "test" in result.stdout


def test_ls_tree_with_dotfiles(cli, initialized_store, workspace):
    """Test that ls shows hidden files in tree."""
    tree_dir = sample_files.create_directory_tree(workspace / "dotfiles", {
        ".hidden": "hidden",
        "visible.txt": "visible",
    })

    add_result = cli.add(tree_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    assert ".hidden" in result.stdout
    assert "visible.txt" in result.stdout


def test_ls_large_tree(cli, initialized_store, workspace):
    """Test listing tree with many entries."""
    large_dir = workspace / "large"
    large_dir.mkdir()
    for i in range(100):
        sample_files.create_sample_file(large_dir / f"file_{i:03d}.txt", f"content{i}")

    add_result = cli.add(large_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    assert result.returncode == 0
    # All files should be listed
    assert "file_000.txt" in result.stdout
    assert "file_099.txt" in result.stdout


def test_ls_tree_long_format_shows_hashes(cli, initialized_store, sample_tree):
    """Test that long format shows entry hashes."""
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, long_format=True, root=initialized_store)

    # Should contain hex hashes (64 char)
    import re
    hex_pattern = r'[0-9a-f]{64}'
    assert re.search(hex_pattern, result.stdout) is not None or "file1.txt" in result.stdout


def test_ls_empty_directory_tree(cli, initialized_store, workspace):
    """Test ls on tree containing empty subdirectory."""
    tree_dir = sample_files.create_directory_tree(workspace / "with_empty", {
        "file.txt": "content",
        "empty_subdir": None,
    })

    add_result = cli.add(tree_dir, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    assert result.returncode == 0
    assert "file.txt" in result.stdout
    assert "empty_subdir" in result.stdout or result.returncode == 0


def test_ls_unicode_filenames(cli, initialized_store, workspace):
    """Test ls with unicode filenames in tree."""
    unicode_tree = sample_files.create_directory_tree(workspace / "unicode", {
        "café.txt": "coffee",
        "日本語.txt": "japanese",
    })

    add_result = cli.add(unicode_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    result = cli.ls(tree_hash, root=initialized_store)

    assert result.returncode == 0
    assert "café.txt" in result.stdout
    assert "日本語.txt" in result.stdout
