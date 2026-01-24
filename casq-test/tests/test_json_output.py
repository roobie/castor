"""Integration tests for JSON output."""

import json
import subprocess
import tempfile
from pathlib import Path
import pytest


# Get the casq binary path from the conftest fixture
@pytest.fixture(scope="module")
def casq_bin(casq_binary):
    """Path to casq binary."""
    return str(casq_binary)


def run_casq(casq_bin, *args, **kwargs):
    """Run casq command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [casq_bin, *args],
        capture_output=True,
        text=True,
        **kwargs
    )
    return result.returncode, result.stdout, result.stderr


def run_casq_json(casq_bin, *args, **kwargs):
    """Run casq with --json flag and return (returncode, json_data, stderr)."""
    returncode, stdout, stderr = run_casq(casq_bin, "--json", *args, **kwargs)
    json_data = None
    if stdout.strip():
        json_data = json.loads(stdout)
    return returncode, json_data, stderr


def test_json_init(casq_bin):
    """Test init command with JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "init")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert str(store_path) in data["root"]
        assert data["algorithm"] == "blake3-256"


def test_json_add_file(casq_bin):
    """Test add command with JSON output for a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Hello World")

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "add", str(test_file))

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert len(data["objects"]) == 1
        assert "hash" in data["objects"][0]
        assert data["objects"][0]["path"] == str(test_file)
        assert data.get("reference") is None


def test_json_add_with_ref(casq_bin):
    """Test add command with --ref-name creates a reference in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Test content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, data, stderr = run_casq_json(casq_bin, 
            "--root", str(store_path), "add", str(test_file), "--ref-name", "myref"
        )

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["reference"] is not None
        assert data["reference"]["name"] == "myref"
        assert "hash" in data["reference"]


def test_json_add_stdin(casq_bin):
    """Test add from stdin with JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, data, stderr = run_casq_json(casq_bin, 
            "--root", str(store_path), "add", "-",
            input="Hello from stdin"
        )

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert len(data["objects"]) == 1
        assert data["objects"][0]["path"] == "(stdin)"


def test_json_ls_refs_empty(casq_bin):
    """Test ls command with no refs in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "ls")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["type"] == "RefList"
        assert data["refs"] == []


def test_json_ls_refs_with_content(casq_bin):
    """Test ls command with refs in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        run_casq(casq_bin, "--root", str(store_path), "add", str(test_file), "--ref-name", "myref")
        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "ls")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["type"] == "RefList"
        assert len(data["refs"]) == 1
        assert data["refs"][0]["name"] == "myref"
        assert "hash" in data["refs"][0]


def test_json_ls_blob(casq_bin):
    """Test ls command on a blob in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Blob content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        _, stdout, _ = run_casq(casq_bin, "--root", str(store_path), "add", str(test_file))
        blob_hash = stdout.split()[0]

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "ls", blob_hash)

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["type"] == "BlobInfo"
        assert data["hash"] == blob_hash
        assert data["size"] > 0


def test_json_ls_tree(casq_bin):
    """Test ls command on a tree in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_dir = Path(tmpdir) / "testdir"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("File 1")
        (test_dir / "file2.txt").write_text("File 2")

        run_casq(casq_bin, "--root", str(store_path), "init")
        _, stdout, _ = run_casq(casq_bin, "--root", str(store_path), "add", str(test_dir))
        tree_hash = stdout.split()[0]

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "ls", tree_hash)

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["type"] == "TreeContents"
        assert data["hash"] == tree_hash
        assert len(data["entries"]) == 2
        names = {e["name"] for e in data["entries"]}
        assert "file1.txt" in names
        assert "file2.txt" in names


def test_json_ls_tree_long(casq_bin):
    """Test ls --long on a tree includes mode and hash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_dir = Path(tmpdir) / "testdir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("Content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        _, stdout, _ = run_casq(casq_bin, "--root", str(store_path), "add", str(test_dir))
        tree_hash = stdout.split()[0]

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "ls", "--long", tree_hash)

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert len(data["entries"]) == 1
        entry = data["entries"][0]
        assert "mode" in entry
        assert entry["mode"] is not None
        assert "hash" in entry
        assert entry["hash"] is not None


def test_json_stat_blob(casq_bin):
    """Test stat command on a blob in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Test content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        _, stdout, _ = run_casq(casq_bin, "--root", str(store_path), "add", str(test_file))
        blob_hash = stdout.split()[0]

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "stat", blob_hash)

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["type"] == "Blob"
        assert data["hash"] == blob_hash
        assert data["size"] > 0
        assert data["size_on_disk"] > 0
        assert "path" in data


def test_json_stat_tree(casq_bin):
    """Test stat command on a tree in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_dir = Path(tmpdir) / "testdir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("Content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        _, stdout, _ = run_casq(casq_bin, "--root", str(store_path), "add", str(test_dir))
        tree_hash = stdout.split()[0]

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "stat", tree_hash)

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["type"] == "Tree"
        assert data["hash"] == tree_hash
        assert data["entry_count"] == 1
        assert "path" in data


def test_json_materialize(casq_bin):
    """Test materialize command with JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Test content")
        dest_path = Path(tmpdir) / "restored.txt"

        run_casq(casq_bin, "--root", str(store_path), "init")
        _, stdout, _ = run_casq(casq_bin, "--root", str(store_path), "add", str(test_file))
        blob_hash = stdout.split()[0]

        returncode, data, stderr = run_casq_json(casq_bin, 
            "--root", str(store_path), "materialize", blob_hash, str(dest_path)
        )

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["hash"] == blob_hash
        assert str(dest_path) in data["destination"]
        assert dest_path.exists()
        assert dest_path.read_text() == "Test content"


def test_json_cat_error(casq_bin):
    """Test cat command with --json returns error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        _, stdout, _ = run_casq(casq_bin, "--root", str(store_path), "add", str(test_file))
        blob_hash = stdout.split()[0]

        returncode, stdout_txt, stderr = run_casq_json(casq_bin, "--root", str(store_path), "cat", blob_hash)

        assert returncode == 1
        # Error should be in stderr as JSON
        error_data = json.loads(stderr)
        assert error_data["success"] is False
        assert error_data["result_code"] == 1
        assert "binary data" in error_data["error"].lower() or "cat" in error_data["error"].lower()


def test_json_gc_dry_run(casq_bin):
    """Test gc --dry-run with JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Orphan content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        run_casq(casq_bin, "--root", str(store_path), "add", str(test_file))  # No ref

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "gc", "--dry-run")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["dry_run"] is True
        assert data["objects_deleted"] >= 0
        assert data["bytes_freed"] >= 0


def test_json_gc(casq_bin):
    """Test gc command with JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "gc")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["dry_run"] is False
        assert "objects_deleted" in data
        assert "bytes_freed" in data


def test_json_orphans_empty(casq_bin):
    """Test orphans command with no orphans in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "orphans")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["orphans"] == []


def test_json_orphans_with_orphan(casq_bin):
    """Test orphans command with an orphaned tree in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_dir = Path(tmpdir) / "testdir"
        test_dir.mkdir()
        (test_dir / "file.txt").write_text("Content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        run_casq(casq_bin, "--root", str(store_path), "add", str(test_dir))  # No ref

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "orphans")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert len(data["orphans"]) == 1
        orphan = data["orphans"][0]
        assert "hash" in orphan
        assert orphan["entry_count"] > 0
        assert orphan["approx_size"] > 0


def test_json_journal_empty(casq_bin):
    """Test journal command with no entries in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "journal")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["entries"] == []


def test_json_journal_with_entries(casq_bin):
    """Test journal command with entries in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        run_casq(casq_bin, "--root", str(store_path), "add", str(test_file))

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "journal")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert len(data["entries"]) >= 1
        entry = data["entries"][0]
        assert "timestamp" in entry
        assert "timestamp_human" in entry
        assert entry["operation"] == "add"
        assert "hash" in entry
        assert "path" in entry


def test_json_refs_add(casq_bin):
    """Test refs add command with JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        _, stdout, _ = run_casq(casq_bin, "--root", str(store_path), "add", str(test_file))
        blob_hash = stdout.split()[0]

        returncode, data, stderr = run_casq_json(casq_bin, 
            "--root", str(store_path), "refs", "add", "myref", blob_hash
        )

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["name"] == "myref"
        assert data["hash"] == blob_hash


def test_json_refs_list_empty(casq_bin):
    """Test refs list with no refs in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "refs", "list")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["refs"] == []


def test_json_refs_list_with_refs(casq_bin):
    """Test refs list with refs in JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        _, stdout, _ = run_casq(casq_bin, "--root", str(store_path), "add", str(test_file), "--ref-name", "myref")

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "refs", "list")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert len(data["refs"]) == 1
        assert data["refs"][0]["name"] == "myref"


def test_json_refs_rm(casq_bin):
    """Test refs rm command with JSON output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        run_casq(casq_bin, "--root", str(store_path), "add", str(test_file), "--ref-name", "myref")

        returncode, data, stderr = run_casq_json(casq_bin, "--root", str(store_path), "refs", "rm", "myref")

        assert returncode == 0
        assert data is not None
        assert data["success"] is True
        assert data["result_code"] == 0
        assert data["name"] == "myref"


def test_json_error_invalid_hash(casq_bin):
    """Test that errors are formatted as JSON when using --json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, stdout_txt, stderr = run_casq_json(casq_bin, 
            "--root", str(store_path), "stat", "invalid_hash"
        )

        assert returncode == 1
        # Error should be in stderr as JSON
        error_data = json.loads(stderr)
        assert error_data["success"] is False
        assert error_data["result_code"] == 1
        assert "error" in error_data


def test_backward_compatibility_text_output(casq_bin):
    """Test that default (text) output still works without --json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("Test content")

        run_casq(casq_bin, "--root", str(store_path), "init")
        returncode, stdout, stderr = run_casq(casq_bin, "--root", str(store_path), "add", str(test_file))

        assert returncode == 0
        # Should be text, not JSON
        assert not stdout.strip().startswith("{")
        assert test_file.name in stdout
        # Should have a hash (64 hex characters)
        words = stdout.split()
        assert any(len(word) == 64 and all(c in "0123456789abcdef" for c in word) for word in words)


def test_json_valid_structure(casq_bin):
    """Test that all JSON outputs have valid structure with success and result_code."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store_path = Path(tmpdir) / "store"

        # Test init
        _, data, _ = run_casq_json(casq_bin, "--root", str(store_path), "init")
        assert "success" in data
        assert "result_code" in data

        # Test ls (refs)
        _, data, _ = run_casq_json(casq_bin, "--root", str(store_path), "ls")
        assert "success" in data
        assert "result_code" in data

        # Test gc
        _, data, _ = run_casq_json(casq_bin, "--root", str(store_path), "gc", "--dry-run")
        assert "success" in data
        assert "result_code" in data

        # Test orphans
        _, data, _ = run_casq_json(casq_bin, "--root", str(store_path), "orphans")
        assert "success" in data
        assert "result_code" in data

        # Test journal
        _, data, _ = run_casq_json(casq_bin, "--root", str(store_path), "journal")
        assert "success" in data
        assert "result_code" in data

        # Test refs list
        _, data, _ = run_casq_json(casq_bin, "--root", str(store_path), "refs", "list")
        assert "success" in data
        assert "result_code" in data
