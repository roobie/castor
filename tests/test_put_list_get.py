"""
Tests for core casq workflow: put, list, get, materialize.
"""

import json
from pathlib import Path
from .helpers import run_casq, assert_json_success, write_test_file, write_test_tree


def test_put_single_file(casq_env):
    """Test putting a single file to the store."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Create test file
    workspace = root.parent / "workspace"
    workspace.mkdir()
    test_file = workspace / "file.txt"
    write_test_file(test_file, "hello world\n")

    # Put file
    proc = run_casq(casq_bin, env, "put", str(test_file))
    assert proc.returncode == 0

    # Should output hash to stdout
    hash_str = proc.stdout.strip()
    assert len(hash_str) == 64  # BLAKE3 hash is 64 hex chars


def test_put_with_json(casq_env):
    """Test putting a file with JSON output."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    workspace = root.parent / "workspace"
    workspace.mkdir()
    test_file = workspace / "file.txt"
    write_test_file(test_file, "test content\n")

    proc = run_casq(casq_bin, env, "--json", "put", str(test_file))
    assert proc.returncode == 0

    data = assert_json_success(proc.stdout, ["object"])
    assert "hash" in data["object"]
    assert data["object"]["path"] == str(test_file)


def test_put_directory_tree(casq_env):
    """Test putting a directory tree."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    workspace = root.parent / "workspace"
    workspace.mkdir()
    write_test_tree(workspace)

    proc = run_casq(casq_bin, env, "put", str(workspace))
    assert proc.returncode == 0

    hash_str = proc.stdout.strip()
    assert len(hash_str) == 64


def test_put_with_reference(casq_env):
    """Test putting a file and creating a reference."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    workspace = root.parent / "workspace"
    workspace.mkdir()
    test_file = workspace / "file.txt"
    write_test_file(test_file, "referenced content\n")

    proc = run_casq(casq_bin, env, "put", str(test_file), "--reference", "test-ref")
    assert proc.returncode == 0

    # Reference name should be in stderr
    assert "test-ref" in proc.stderr

    # Verify reference was created
    assert (root / "refs" / "test-ref").exists()


def test_put_from_stdin(casq_env):
    """Test putting content from stdin using '-'."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    content = "stdin test content\n"
    proc = run_casq(casq_bin, env, "put", "-", input=content)
    assert proc.returncode == 0

    hash_str = proc.stdout.strip()
    assert len(hash_str) == 64


def test_get_blob_to_stdout(casq_env):
    """Test getting a blob's content to stdout."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Put content
    content = "blob content for get test\n"
    proc_put = run_casq(casq_bin, env, "put", "-", input=content)
    hash_str = proc_put.stdout.strip()

    # Get content back
    proc_get = run_casq(casq_bin, env, "get", hash_str)
    assert proc_get.returncode == 0
    assert proc_get.stdout == content


def test_get_with_json_fails(casq_env):
    """Test that get with --json flag fails with helpful message."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Put content
    proc_put = run_casq(casq_bin, env, "put", "-", input="test\n")
    hash_str = proc_put.stdout.strip()

    # Try get with --json (should fail)
    proc_get = run_casq(casq_bin, env, "--json", "get", hash_str)
    assert proc_get.returncode != 0
    assert "cannot be used with --json" in proc_get.stderr


def test_list_tree_contents(casq_env):
    """Test listing tree contents."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Create and put directory tree
    workspace = root.parent / "workspace"
    workspace.mkdir()
    write_test_tree(workspace)

    proc_put = run_casq(casq_bin, env, "put", str(workspace))
    tree_hash = proc_put.stdout.strip()

    # List tree contents
    proc_list = run_casq(casq_bin, env, "list", tree_hash)
    assert proc_list.returncode == 0
    assert "file1.txt" in proc_list.stdout
    assert "file2.txt" in proc_list.stdout
    assert "subdir" in proc_list.stdout


def test_list_tree_long_format(casq_env):
    """Test listing tree contents with --long flag."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    workspace = root.parent / "workspace"
    workspace.mkdir()
    write_test_tree(workspace)

    proc_put = run_casq(casq_bin, env, "put", str(workspace))
    tree_hash = proc_put.stdout.strip()

    # List with --long
    proc_list = run_casq(casq_bin, env, "list", tree_hash, "--long")
    assert proc_list.returncode == 0

    # Should include mode, type, and hash
    assert "file1.txt" in proc_list.stdout
    # Should show type indicator (b for blob, t for tree)
    assert "b " in proc_list.stdout or "t " in proc_list.stdout


def test_list_blob_shows_info(casq_env):
    """Test that listing a blob shows blob info."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc_put = run_casq(casq_bin, env, "put", "-", input="test blob\n")
    blob_hash = proc_put.stdout.strip()

    proc_list = run_casq(casq_bin, env, "list", blob_hash)
    assert proc_list.returncode == 0
    assert "blob" in proc_list.stdout


def test_materialize_blob(casq_env):
    """Test materializing a blob to filesystem."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    content = "materialize test content\n"
    proc_put = run_casq(casq_bin, env, "put", "-", input=content)
    hash_str = proc_put.stdout.strip()

    # Materialize to destination
    dest = root.parent / "output.txt"
    proc_mat = run_casq(casq_bin, env, "materialize", hash_str, str(dest))
    assert proc_mat.returncode == 0

    # Verify content
    assert dest.exists()
    assert dest.read_text() == content


def test_materialize_tree(casq_env):
    """Test materializing a tree to filesystem."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Create and put tree
    workspace = root.parent / "workspace"
    workspace.mkdir()
    write_test_tree(workspace)

    proc_put = run_casq(casq_bin, env, "put", str(workspace))
    tree_hash = proc_put.stdout.strip()

    # Materialize to new location
    dest = root.parent / "restored"
    proc_mat = run_casq(casq_bin, env, "materialize", tree_hash, str(dest))
    assert proc_mat.returncode == 0

    # Verify structure
    assert (dest / "file1.txt").exists()
    assert (dest / "file2.txt").exists()
    assert (dest / "subdir" / "nested.txt").exists()
    assert (dest / "file1.txt").read_text() == "file 1 content\n"


def test_roundtrip_integrity(casq_env):
    """Test that put + get maintains data integrity."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    original_content = "Round-trip integrity test\nWith multiple lines\nAnd special chars: \x00\x01\xff\n"

    # Put content
    proc_put = run_casq(casq_bin, env, "put", "-", input=original_content)
    hash_str = proc_put.stdout.strip()

    # Get content back
    proc_get = run_casq(casq_bin, env, "get", hash_str)
    assert proc_get.returncode == 0
    assert proc_get.stdout == original_content
