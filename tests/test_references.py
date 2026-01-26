"""
Tests for reference management (references add/list/remove).
"""

import json
from .helpers import run_casq, assert_json_success


def test_references_list_empty(casq_env):
    """Test listing references in empty store."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc_list = run_casq(casq_bin, env, "references", "list")
    assert proc_list.returncode == 0
    assert "No references" in proc_list.stderr
    assert proc_list.stdout == ""


def test_references_add(casq_env):
    """Test adding a reference."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Put an object
    proc_put = run_casq(casq_bin, env, "put", "-", input="ref test\n")
    obj_hash = proc_put.stdout.strip()

    # Add reference
    proc_add = run_casq(casq_bin, env, "references", "add", "my-ref", obj_hash)
    assert proc_add.returncode == 0
    assert "my-ref" in proc_add.stderr or obj_hash in proc_add.stderr

    # Verify reference file exists
    assert (root / "refs" / "my-ref").exists()


def test_references_list_shows_added(casq_env):
    """Test that list shows added references."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add reference
    proc_put = run_casq(casq_bin, env, "put", "-", input="test\n")
    obj_hash = proc_put.stdout.strip()
    run_casq(casq_bin, env, "references", "add", "test-ref", obj_hash)

    # List references
    proc_list = run_casq(casq_bin, env, "references", "list")
    assert proc_list.returncode == 0
    assert "test-ref" in proc_list.stdout
    assert obj_hash in proc_list.stdout


def test_references_list_json(casq_env):
    """Test listing references with JSON output."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add reference
    proc_put = run_casq(casq_bin, env, "put", "-", input="json ref test\n")
    obj_hash = proc_put.stdout.strip()
    run_casq(casq_bin, env, "references", "add", "json-ref", obj_hash)

    # List with JSON
    proc_list = run_casq(casq_bin, env, "--json", "references", "list")
    assert proc_list.returncode == 0

    data = assert_json_success(proc_list.stdout, ["refs"])
    assert len(data["refs"]) > 0

    # Find our reference
    ref_found = any(
        r["name"] == "json-ref" and r["hash"] == obj_hash for r in data["refs"]
    )
    assert ref_found


def test_references_add_json(casq_env):
    """Test adding reference with JSON output."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc_put = run_casq(casq_bin, env, "put", "-", input="test\n")
    obj_hash = proc_put.stdout.strip()

    proc_add = run_casq(
        casq_bin, env, "--json", "references", "add", "new-ref", obj_hash
    )
    assert proc_add.returncode == 0

    data = assert_json_success(proc_add.stdout, ["name", "hash"])
    assert data["name"] == "new-ref"
    assert data["hash"] == obj_hash


def test_references_remove(casq_env):
    """Test removing a reference."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add reference
    proc_put = run_casq(casq_bin, env, "put", "-", input="will remove\n")
    obj_hash = proc_put.stdout.strip()
    run_casq(casq_bin, env, "references", "add", "temp-ref", obj_hash)

    # Verify it exists
    assert (root / "refs" / "temp-ref").exists()

    # Remove reference
    proc_rm = run_casq(casq_bin, env, "references", "remove", "temp-ref")
    assert proc_rm.returncode == 0
    assert "Removed" in proc_rm.stderr or "temp-ref" in proc_rm.stderr

    # Verify it's gone
    assert not (root / "refs" / "temp-ref").exists()


def test_references_remove_json(casq_env):
    """Test removing reference with JSON output."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add and remove reference
    proc_put = run_casq(casq_bin, env, "put", "-", input="test\n")
    obj_hash = proc_put.stdout.strip()
    run_casq(casq_bin, env, "references", "add", "temp", obj_hash)

    proc_rm = run_casq(casq_bin, env, "--json", "references", "remove", "temp")
    assert proc_rm.returncode == 0

    data = assert_json_success(proc_rm.stdout, ["name"])
    assert data["name"] == "temp"


def test_references_remove_nonexistent(casq_env):
    """Test removing non-existent reference returns error."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc_rm = run_casq(casq_bin, env, "references", "remove", "does-not-exist")
    assert proc_rm.returncode != 0


def test_references_add_multiple(casq_env):
    """Test adding multiple references."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add object
    proc_put = run_casq(casq_bin, env, "put", "-", input="multi-ref test\n")
    obj_hash = proc_put.stdout.strip()

    # Add multiple references to same object
    run_casq(casq_bin, env, "references", "add", "ref1", obj_hash)
    run_casq(casq_bin, env, "references", "add", "ref2", obj_hash)
    run_casq(casq_bin, env, "references", "add", "ref3", obj_hash)

    # List should show all three
    proc_list = run_casq(casq_bin, env, "references", "list")
    assert proc_list.returncode == 0
    assert "ref1" in proc_list.stdout
    assert "ref2" in proc_list.stdout
    assert "ref3" in proc_list.stdout


def test_references_prevent_gc(casq_env):
    """Test that references prevent garbage collection."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add object with reference
    proc_put = run_casq(casq_bin, env, "put", "-", input="protected\n")
    obj_hash = proc_put.stdout.strip()
    run_casq(casq_bin, env, "references", "add", "protect", obj_hash)

    # Run GC
    run_casq(casq_bin, env, "collect-garbage")

    # Object should still be accessible
    proc_get = run_casq(casq_bin, env, "get", obj_hash)
    assert proc_get.returncode == 0
    assert proc_get.stdout == "protected\n"

    # Remove reference and GC again
    run_casq(casq_bin, env, "references", "remove", "protect")
    run_casq(casq_bin, env, "collect-garbage")

    # Now object should be gone
    proc_get2 = run_casq(casq_bin, env, "get", obj_hash)
    assert proc_get2.returncode != 0
