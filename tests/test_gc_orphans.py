"""
Tests for garbage collection and orphan detection.
"""

import json
from .helpers import run_casq, assert_json_success, write_test_file


def test_collect_garbage_empty_store(casq_env):
    """Test GC on empty store."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc_gc = run_casq(casq_bin, env, "collect-garbage")
    assert proc_gc.returncode == 0
    assert "0" in proc_gc.stdout  # Should delete 0 objects


def test_collect_garbage_dry_run(casq_env):
    """Test GC dry-run mode."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add object without reference (will be orphaned)
    workspace = root.parent / "workspace"
    workspace.mkdir()
    test_file = workspace / "file.txt"
    write_test_file(test_file, "orphan content\n")

    run_casq(casq_bin, env, "put", str(test_file))

    # Dry run GC
    proc_gc = run_casq(casq_bin, env, "collect-garbage", "--dry-run")
    assert proc_gc.returncode == 0
    assert "Dry run" in proc_gc.stdout or "Would delete" in proc_gc.stdout


def test_collect_garbage_removes_orphans(casq_env):
    """Test that GC removes unreferenced objects."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add object without reference
    proc_put = run_casq(casq_bin, env, "put", "-", input="orphan\n")
    orphan_hash = proc_put.stdout.strip()

    # Verify object exists
    objects_dir = root / "objects" / "blake3-256"
    assert objects_dir.exists()

    # Count objects before GC
    import os

    obj_count_before = sum(1 for _ in objects_dir.rglob("*") if _.is_file())
    assert obj_count_before > 0

    # Run GC
    proc_gc = run_casq(casq_bin, env, "collect-garbage")
    assert proc_gc.returncode == 0

    # Should have deleted the orphan
    output = proc_gc.stdout
    assert "Deleted" in output or "deleted" in output


def test_collect_garbage_keeps_referenced(casq_env):
    """Test that GC keeps objects with references."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add object with reference
    proc_put = run_casq(
        casq_bin, env, "put", "-", "--reference", "keep-me", input="important data\n"
    )
    kept_hash = proc_put.stdout.strip()

    # Run GC
    proc_gc = run_casq(casq_bin, env, "collect-garbage")
    assert proc_gc.returncode == 0

    # Object should still exist
    proc_get = run_casq(casq_bin, env, "get", kept_hash)
    assert proc_get.returncode == 0
    assert proc_get.stdout == "important data\n"


def test_collect_garbage_json_output(casq_env):
    """Test GC with JSON output."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add orphan
    run_casq(casq_bin, env, "put", "-", input="orphan\n")

    proc_gc = run_casq(casq_bin, env, "--json", "collect-garbage")
    assert proc_gc.returncode == 0

    data = assert_json_success(proc_gc.stdout, ["objects_deleted", "bytes_freed"])
    assert data["dry_run"] is False
    assert data["objects_deleted"] >= 1
    assert data["bytes_freed"] > 0


def test_find_orphans_empty_store(casq_env):
    """Test finding orphans in empty store."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc_orphans = run_casq(casq_bin, env, "find-orphans")
    assert proc_orphans.returncode == 0
    assert "No orphaned objects" in proc_orphans.stderr or proc_orphans.stdout == ""


def test_find_orphans_detects_unreferenced(casq_env):
    """Test that find-orphans detects unreferenced objects."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add object without reference
    proc_put = run_casq(casq_bin, env, "put", "-", input="orphan data\n")
    orphan_hash = proc_put.stdout.strip()

    proc_orphans = run_casq(casq_bin, env, "find-orphans")
    assert proc_orphans.returncode == 0
    assert orphan_hash in proc_orphans.stdout


def test_find_orphans_long_format(casq_env):
    """Test find-orphans with --long flag."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add orphan
    proc_put = run_casq(casq_bin, env, "put", "-", input="orphan\n")
    orphan_hash = proc_put.stdout.strip()

    proc_orphans = run_casq(casq_bin, env, "find-orphans", "--long")
    assert proc_orphans.returncode == 0

    output = proc_orphans.stdout
    assert orphan_hash in output
    assert "Hash:" in output
    assert "Type:" in output
    assert "Approx size:" in output


def test_find_orphans_ignores_referenced(casq_env):
    """Test that find-orphans ignores referenced objects."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add object with reference
    proc_put = run_casq(
        casq_bin,
        env,
        "put",
        "-",
        "--reference",
        "not-orphan",
        input="referenced data\n",
    )
    ref_hash = proc_put.stdout.strip()

    proc_orphans = run_casq(casq_bin, env, "find-orphans")
    assert proc_orphans.returncode == 0

    # Referenced object should NOT appear in orphans
    assert ref_hash not in proc_orphans.stdout


def test_find_orphans_json_output(casq_env):
    """Test find-orphans with JSON output."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add orphan
    proc_put = run_casq(casq_bin, env, "put", "-", input="orphan json test\n")
    orphan_hash = proc_put.stdout.strip()

    proc_orphans = run_casq(casq_bin, env, "--json", "find-orphans")
    assert proc_orphans.returncode == 0

    data = assert_json_success(proc_orphans.stdout, ["orphans"])
    assert len(data["orphans"]) > 0

    # Find our orphan in the list
    orphan_found = any(o["hash"] == orphan_hash for o in data["orphans"])
    assert orphan_found


def test_gc_then_find_orphans_empty(casq_env):
    """Test that find-orphans shows nothing after GC."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Add orphan
    run_casq(casq_bin, env, "put", "-", input="will be collected\n")

    # Run GC
    proc_gc = run_casq(casq_bin, env, "collect-garbage")
    assert proc_gc.returncode == 0

    # Find orphans should be empty
    proc_orphans = run_casq(casq_bin, env, "find-orphans")
    assert proc_orphans.returncode == 0
    assert "No orphaned objects" in proc_orphans.stderr or proc_orphans.stdout == ""
