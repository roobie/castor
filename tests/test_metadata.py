"""
Tests for casq metadata command.
"""
import json
from .helpers import run_casq, assert_json_success, write_test_file, write_test_tree


def test_metadata_for_blob(casq_env):
    """Test getting metadata for a blob object."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    content = "metadata test blob\n"
    proc_put = run_casq(casq_bin, env, "put", "-", input=content)
    blob_hash = proc_put.stdout.strip()

    # Get metadata
    proc_meta = run_casq(casq_bin, env, "metadata", blob_hash)
    assert proc_meta.returncode == 0

    output = proc_meta.stdout
    assert "Hash:" in output
    assert "Type: blob" in output
    assert "Size:" in output
    assert blob_hash in output


def test_metadata_for_tree(casq_env):
    """Test getting metadata for a tree object."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    workspace = root.parent / "workspace"
    workspace.mkdir()
    write_test_tree(workspace)

    proc_put = run_casq(casq_bin, env, "put", str(workspace))
    tree_hash = proc_put.stdout.strip()

    # Get metadata
    proc_meta = run_casq(casq_bin, env, "metadata", tree_hash)
    assert proc_meta.returncode == 0

    output = proc_meta.stdout
    assert "Hash:" in output
    assert "Type: tree" in output
    assert "Entries:" in output
    assert tree_hash in output


def test_metadata_json_output(casq_env):
    """Test metadata command with JSON output."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    content = "json metadata test\n"
    proc_put = run_casq(casq_bin, env, "put", "-", input=content)
    blob_hash = proc_put.stdout.strip()

    proc_meta = run_casq(casq_bin, env, "--json", "metadata", blob_hash)
    assert proc_meta.returncode == 0

    data = assert_json_success(proc_meta.stdout, ["hash", "size"])

    # Check blob-specific fields
    assert data["hash"] == blob_hash
    assert data["size"] == len(content)
    assert "size_on_disk" in data


def test_metadata_tree_json(casq_env):
    """Test metadata for tree with JSON output."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    workspace = root.parent / "workspace"
    workspace.mkdir()
    write_test_tree(workspace)

    proc_put = run_casq(casq_bin, env, "put", str(workspace))
    tree_hash = proc_put.stdout.strip()

    proc_meta = run_casq(casq_bin, env, "--json", "metadata", tree_hash)
    assert proc_meta.returncode == 0

    data = assert_json_success(proc_meta.stdout, ["hash"])
    assert data["hash"] == tree_hash
    assert "entry_count" in data
    # Should have at least 3 entries (file1, file2, subdir)
    assert data["entry_count"] >= 3


def test_metadata_nonexistent_hash(casq_env):
    """Test metadata with non-existent hash returns error."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    fake_hash = "0" * 64
    proc_meta = run_casq(casq_bin, env, "metadata", fake_hash)

    assert proc_meta.returncode != 0
    assert "not found" in proc_meta.stderr.lower() or "not found" in proc_meta.stdout.lower()


def test_metadata_invalid_hash(casq_env):
    """Test metadata with invalid hash format returns error."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    invalid_hash = "notahash"
    proc_meta = run_casq(casq_bin, env, "metadata", invalid_hash)

    assert proc_meta.returncode != 0
    assert "invalid" in proc_meta.stderr.lower() or "invalid" in proc_meta.stdout.lower()
