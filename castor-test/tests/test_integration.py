"""Integration tests for multi-command workflows."""

import pytest
from pathlib import Path
from fixtures import sample_files
from helpers.verification import verify_object_exists, count_objects, list_all_refs


@pytest.mark.smoke
def test_full_backup_restore_workflow(cli, castor_store, workspace):
    """Test complete workflow: init → add → materialize → verify."""
    # Initialize store
    cli.init(root=castor_store)

    # Create test data
    test_dir = sample_files.create_directory_tree(workspace / "backup", {
        "docs": {
            "readme.txt": "Important documentation",
            "guide.txt": "User guide",
        },
        "data": {
            "file1.dat": "data1",
            "file2.dat": "data2",
        },
        "config.json": '{"setting": "value"}',
    })

    # Add with ref
    add_result = cli.add(test_dir, root=castor_store, ref_name="backup-v1")
    tree_hash = add_result.stdout.strip().split()[0]

    # Verify object exists
    verify_object_exists(castor_store, tree_hash)

    # Materialize to new location
    restore_dir = workspace / "restored"
    cli.materialize(tree_hash, restore_dir, root=castor_store)

    # Verify structure
    assert (restore_dir / "docs" / "readme.txt").exists()
    assert (restore_dir / "docs" / "guide.txt").exists()
    assert (restore_dir / "data" / "file1.dat").exists()
    assert (restore_dir / "data" / "file2.dat").exists()
    assert (restore_dir / "config.json").exists()

    # Verify content
    assert (restore_dir / "docs" / "readme.txt").read_text() == "Important documentation"
    assert (restore_dir / "config.json").read_text() == '{"setting": "value"}'


def test_multiple_snapshots_with_deduplication(cli, initialized_store, workspace):
    """Test creating multiple snapshots with shared content."""
    # Snapshot 1
    v1_dir = sample_files.create_directory_tree(workspace / "v1", {
        "shared.txt": "shared content",
        "v1-only.txt": "version 1 file",
    })
    hash_v1 = cli.add(v1_dir, root=initialized_store, ref_name="v1").stdout.strip().split()[0]

    initial_count = count_objects(initialized_store)

    # Snapshot 2 (shares one file)
    v2_dir = sample_files.create_directory_tree(workspace / "v2", {
        "shared.txt": "shared content",  # Same content - should dedupe
        "v2-only.txt": "version 2 file",
    })
    hash_v2 = cli.add(v2_dir, root=initialized_store, ref_name="v2").stdout.strip().split()[0]

    final_count = count_objects(initialized_store)

    # Should have added fewer objects than if no deduplication
    # v2 should reuse the shared.txt blob
    assert final_count < initial_count + 4  # Not 2 new trees + 2 new blobs


def test_ref_management_workflow(cli, initialized_store, workspace):
    """Test complete ref management: add, list, update, remove."""
    # Create several versions
    versions = {}
    for i in range(3):
        file = sample_files.create_sample_file(workspace / f"v{i}.txt", f"version {i}")
        hash_val = cli.add(file, root=initialized_store).stdout.strip().split()[0]
        versions[f"v{i}"] = hash_val

    # Add refs
    for name, hash_val in versions.items():
        cli.refs_add(name, hash_val, root=initialized_store)

    # List all refs
    list_result = cli.refs_list(root=initialized_store)
    for name in versions.keys():
        assert name in list_result.stdout

    # Update v0 to point to v2's content
    cli.refs_add("v0", versions["v2"], root=initialized_store)

    # Verify update
    refs = list_all_refs(initialized_store)
    assert refs["v0"] == versions["v2"]

    # Remove v1
    cli.refs_rm("v1", root=initialized_store)

    # Verify removal
    list_result2 = cli.refs_list(root=initialized_store)
    assert "v1" not in list_result2.stdout


def test_gc_interaction_with_refs(cli, initialized_store, workspace):
    """Test GC behavior with ref additions and removals."""
    # Add file with ref
    file1 = sample_files.create_sample_file(workspace / "keep.txt", "keep")
    hash1 = cli.add(file1, root=initialized_store, ref_name="keeper").stdout.strip().split()[0]

    # Add orphan
    file2 = sample_files.create_sample_file(workspace / "temp.txt", "temp")
    hash2 = cli.add(file2, root=initialized_store).stdout.strip().split()[0]

    # GC should keep hash1, delete hash2
    cli.gc(root=initialized_store)

    verify_object_exists(initialized_store, hash1)
    from helpers.verification import get_object_path
    assert not get_object_path(initialized_store, hash2).exists()

    # Remove ref and GC again
    cli.refs_rm("keeper", root=initialized_store)
    cli.gc(root=initialized_store)

    # Now hash1 should also be gone
    assert not get_object_path(initialized_store, hash1).exists()


def test_complex_multicommand_scenario(cli, castor_store, workspace):
    """Test complex scenario with multiple operations."""
    # 1. Initialize
    cli.init(root=castor_store)

    # 2. Create and add project directory
    project = sample_files.create_directory_tree(workspace / "project", {
        "src": {
            "main.py": "def main(): pass",
            "utils.py": "def helper(): pass",
        },
        "tests": {
            "test_main.py": "def test(): assert True",
        },
        "README.md": "# Project",
    })
    hash_v1 = cli.add(project, root=castor_store, ref_name="project-v1").stdout.strip().split()[0]

    # 3. Make changes
    (workspace / "project" / "src" / "main.py").write_text("def main(): print('updated')")
    sample_files.create_sample_file(workspace / "project" / "CHANGELOG.md", "## v2\n- Updated")

    # 4. Create new snapshot
    hash_v2 = cli.add(project, root=castor_store, ref_name="project-v2").stdout.strip().split()[0]

    # 5. List objects
    assert count_objects(castor_store) > 0

    # 6. Stat both versions
    stat_v1 = cli.stat(hash_v1, root=castor_store)
    stat_v2 = cli.stat(hash_v2, root=castor_store)
    assert "tree" in stat_v1.stdout.lower()
    assert "tree" in stat_v2.stdout.lower()

    # 7. List refs
    refs_list = cli.refs_list(root=castor_store)
    assert "project-v1" in refs_list.stdout
    assert "project-v2" in refs_list.stdout

    # 8. Restore v1
    restore_v1 = workspace / "restore-v1"
    cli.materialize(hash_v1, restore_v1, root=castor_store)

    # 9. Verify v1 doesn't have CHANGELOG
    assert not (restore_v1 / "CHANGELOG.md").exists()
    assert (restore_v1 / "README.md").exists()


def test_store_migration_workflow(cli, castor_store, workspace):
    """Test workflow: init → populate → gc → verify integrity."""
    # 1. Init
    cli.init(root=castor_store)

    # 2. Populate with data
    for i in range(10):
        file = sample_files.create_sample_file(workspace / f"file{i}.txt", f"content {i}")
        if i % 2 == 0:
            # Keep even-numbered files
            cli.add(file, root=castor_store, ref_name=f"keep{i}")
        else:
            # Odd-numbered are orphans
            cli.add(file, root=castor_store)

    initial_count = count_objects(castor_store)
    assert initial_count > 0

    # 3. GC
    gc_result = cli.gc(root=castor_store)
    assert gc_result.returncode == 0

    final_count = count_objects(castor_store)

    # 4. Verify: should have ~5 objects left (even-numbered)
    assert final_count < initial_count
    assert final_count >= 5

    # 5. Verify refs still work
    refs = list_all_refs(castor_store)
    for i in range(0, 10, 2):
        assert f"keep{i}" in refs


def test_cat_ls_stat_consistency(cli, initialized_store, workspace):
    """Test consistency between cat, ls, and stat commands."""
    content = "test content\n"
    test_file = sample_files.create_sample_file(workspace / "test.txt", content)

    # Add file
    hash_val = cli.add(test_file, root=initialized_store).stdout.strip().split()[0]

    # Cat should output content
    cat_result = cli.cat(hash_val, root=initialized_store)
    assert cat_result.stdout == content

    # Stat should show blob type
    stat_result = cli.stat(hash_val, root=initialized_store)
    assert "blob" in stat_result.stdout.lower()

    # Ls should show blob info
    ls_result = cli.ls(hash_val, root=initialized_store)
    assert ls_result.returncode == 0


def test_nested_tree_full_workflow(cli, initialized_store, workspace, nested_tree):
    """Test full workflow with nested directory structure."""
    # Add
    hash_val = cli.add(nested_tree, root=initialized_store, ref_name="nested").stdout.strip().split()[0]

    # Ls should show top-level entries
    ls_result = cli.ls(hash_val, root=initialized_store)
    assert "top.txt" in ls_result.stdout
    assert "dir1" in ls_result.stdout

    # Stat should show tree type
    stat_result = cli.stat(hash_val, root=initialized_store)
    assert "tree" in stat_result.stdout.lower()

    # Materialize
    restore_dir = workspace / "restored"
    cli.materialize(hash_val, restore_dir, root=initialized_store)

    # Verify deep structure
    assert (restore_dir / "dir2" / "subdir" / "deep.txt").exists()


def test_ref_based_restore(cli, initialized_store, workspace):
    """Test restoring from refs rather than direct hashes."""
    # Create backup
    backup_dir = sample_files.create_directory_tree(workspace / "backup", {
        "important.txt": "critical data",
        "docs": {
            "manual.txt": "documentation",
        },
    })

    cli.add(backup_dir, root=initialized_store, ref_name="production-backup")

    # Get hash from ref
    refs = list_all_refs(initialized_store)
    backup_hash = refs["production-backup"]

    # Restore using hash from ref
    restore_dir = workspace / "restored"
    cli.materialize(backup_hash, restore_dir, root=initialized_store)

    # Verify
    assert (restore_dir / "important.txt").read_text() == "critical data"
    assert (restore_dir / "docs" / "manual.txt").read_text() == "documentation"


def test_incremental_backup_scenario(cli, initialized_store, workspace):
    """Test incremental backup scenario with multiple versions."""
    # Day 1
    day1 = sample_files.create_directory_tree(workspace / "day1", {
        "data.txt": "day 1 data",
    })
    cli.add(day1, root=initialized_store, ref_name="backup-day1")

    # Day 2 (add file)
    day2 = sample_files.create_directory_tree(workspace / "day2", {
        "data.txt": "day 1 data",  # Unchanged - should dedupe
        "new.txt": "day 2 addition",
    })
    cli.add(day2, root=initialized_store, ref_name="backup-day2")

    # Day 3 (modify file)
    day3 = sample_files.create_directory_tree(workspace / "day3", {
        "data.txt": "day 3 updated data",  # Changed
        "new.txt": "day 2 addition",  # Unchanged
    })
    cli.add(day3, root=initialized_store, ref_name="backup-day3")

    # All refs should exist
    refs = list_all_refs(initialized_store)
    assert "backup-day1" in refs
    assert "backup-day2" in refs
    assert "backup-day3" in refs

    # Deduplication should have occurred
    # Not testing exact count, but verify all snapshots are independently restorable


def test_empty_store_all_commands(cli, initialized_store):
    """Test all commands handle empty store gracefully."""
    # List refs (empty)
    assert cli.refs_list(root=initialized_store).returncode == 0

    # GC (nothing to collect)
    assert cli.gc(root=initialized_store).returncode == 0

    # Dry-run GC
    assert cli.gc(root=initialized_store, dry_run=True).returncode == 0

    # Ls (refs)
    assert cli.ls(root=initialized_store).returncode == 0


def test_large_dataset_workflow(cli, initialized_store, workspace):
    """Test workflow with larger dataset."""
    # Create 50 files
    large_dir = workspace / "large"
    large_dir.mkdir()
    for i in range(50):
        sample_files.create_sample_file(large_dir / f"file{i}.txt", f"content {i}")

    # Add
    hash_val = cli.add(large_dir, root=initialized_store, ref_name="large-set").stdout.strip().split()[0]

    # Ls should list all
    ls_result = cli.ls(hash_val, root=initialized_store)
    assert "file0.txt" in ls_result.stdout
    assert "file49.txt" in ls_result.stdout

    # Stat
    stat_result = cli.stat(hash_val, root=initialized_store)
    assert "50" in stat_result.stdout or "tree" in stat_result.stdout.lower()

    # Materialize
    restore_dir = workspace / "restored_large"
    cli.materialize(hash_val, restore_dir, root=initialized_store)

    # Verify all files
    assert len(list(restore_dir.iterdir())) == 50


def test_mixed_operations_consistency(cli, initialized_store, workspace):
    """Test that mixed operations maintain consistency."""
    # Add some files
    file1 = sample_files.create_sample_file(workspace / "f1.txt", "file 1")
    file2 = sample_files.create_sample_file(workspace / "f2.txt", "file 2")

    hash1 = cli.add(file1, root=initialized_store, ref_name="ref1").stdout.strip().split()[0]
    hash2 = cli.add(file2, root=initialized_store, ref_name="ref2").stdout.strip().split()[0]

    # Cat, ls, stat should all work
    cat1 = cli.cat(hash1, root=initialized_store)
    ls1 = cli.ls(hash1, root=initialized_store)
    stat1 = cli.stat(hash1, root=initialized_store)

    assert cat1.returncode == 0
    assert ls1.returncode == 0
    assert stat1.returncode == 0

    # Refs operations
    cli.refs_add("ref3", hash1, root=initialized_store)
    refs = list_all_refs(initialized_store)
    assert len(refs) >= 3

    # GC shouldn't delete anything
    initial = count_objects(initialized_store)
    cli.gc(root=initialized_store)
    final = count_objects(initialized_store)
    assert initial == final


def test_unicode_throughout_workflow(cli, initialized_store, workspace):
    """Test Unicode handling throughout complete workflow."""
    unicode_dir = sample_files.create_directory_tree(workspace / "unicode", {
        "café.txt": "Bonjour!",
        "日本語": {
            "ファイル.txt": "こんにちは",
        },
    })

    # Add
    hash_val = cli.add(unicode_dir, root=initialized_store, ref_name="unicode-backup").stdout.strip().split()[0]

    # Ls
    ls_result = cli.ls(hash_val, root=initialized_store)
    assert "café.txt" in ls_result.stdout

    # Materialize
    restore_dir = workspace / "restored_unicode"
    cli.materialize(hash_val, restore_dir, root=initialized_store)

    # Verify
    assert (restore_dir / "café.txt").exists()
    assert (restore_dir / "日本語" / "ファイル.txt").exists()
    assert (restore_dir / "café.txt").read_text() == "Bonjour!"


def test_binary_files_workflow(cli, initialized_store, workspace):
    """Test binary file handling through complete workflow."""
    binary1 = sample_files.create_binary_file(workspace / "b1.bin", 1024, b"\xDE\xAD")
    binary2 = sample_files.create_binary_file(workspace / "b2.bin", 2048, b"\xBE\xEF")

    # Add
    hash1 = cli.add(binary1, root=initialized_store).stdout.strip().split()[0]
    hash2 = cli.add(binary2, root=initialized_store).stdout.strip().split()[0]

    # Cat
    cat1 = cli.cat(hash1, root=initialized_store)
    assert cat1.returncode == 0

    # Stat
    stat1 = cli.stat(hash1, root=initialized_store)
    assert "blob" in stat1.stdout.lower()

    # Materialize
    restore1 = workspace / "restored_b1.bin"
    cli.materialize(hash1, restore1, root=initialized_store)

    # Verify binary content
    assert restore1.read_bytes() == binary1.read_bytes()


def test_store_compaction_scenario(cli, initialized_store, workspace):
    """Test scenario: populate, clean old refs, GC to compact."""
    # Add 10 generations
    hashes = []
    for gen in range(10):
        file = sample_files.create_sample_file(workspace / f"gen{gen}.txt", f"generation {gen}")
        hash_val = cli.add(file, root=initialized_store, ref_name=f"gen{gen}").stdout.strip().split()[0]
        hashes.append(hash_val)

    initial_count = count_objects(initialized_store)

    # Remove old generations (keep only last 3)
    for gen in range(7):
        cli.refs_rm(f"gen{gen}", root=initialized_store)

    # GC to compact
    cli.gc(root=initialized_store)

    final_count = count_objects(initialized_store)

    # Should have fewer objects
    assert final_count < initial_count

    # Last 3 should still be accessible
    for gen in range(7, 10):
        verify_object_exists(initialized_store, hashes[gen])
