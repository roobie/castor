"""Integration tests for stdin support in casq add command."""

import subprocess
import json
from pathlib import Path
import tempfile


def run_casq(*args, stdin_data=None, check=True, cwd=None):
    """Run casq command with optional stdin data."""
    cmd = ["casq"] + list(args)
    result = subprocess.run(
        cmd,
        input=stdin_data,
        capture_output=True,
        text=False,  # Binary mode for stdin
        check=check,
        cwd=cwd,
    )
    return result


def test_stdin_basic(tmp_path):
    """Test basic stdin addition."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Add content via stdin
    content = b"hello from stdin"
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)

    # Should output hash with "(stdin)" label
    output = result.stdout.decode().strip()
    assert "(stdin)" in output
    hash_value = output.split()[0]
    assert len(hash_value) == 64  # BLAKE3 hex length

    # Verify we can retrieve the content
    cat_result = run_casq("cat", hash_value, "--root", str(store))
    assert cat_result.stdout == content


def test_stdin_with_ref_name(tmp_path):
    """Test stdin addition with --ref-name."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Add content via stdin with ref name
    content = b"content with reference"
    result = run_casq(
        "add", "-", "--ref-name", "test-ref", "--root", str(store), stdin_data=content
    )

    output = result.stdout.decode()
    assert "(stdin)" in output
    assert "Created reference: test-ref ->" in output

    # Verify ref was created
    refs_result = run_casq("refs", "list", "--root", str(store))
    refs_output = refs_result.stdout.decode()
    assert "test-ref ->" in refs_output


def test_stdin_empty(tmp_path):
    """Test empty stdin."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Add empty content
    content = b""
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)

    output = result.stdout.decode().strip()
    assert "(stdin)" in output
    hash_value = output.split()[0]

    # Verify empty content is stored correctly
    cat_result = run_casq("cat", hash_value, "--root", str(store))
    assert cat_result.stdout == b""


def test_stdin_binary_data(tmp_path):
    """Test binary data with null bytes."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Binary content with null bytes
    content = b"\x00\x01\x02\xff\xfe\xfd"
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)

    output = result.stdout.decode().strip()
    hash_value = output.split()[0]

    # Verify binary content preserved exactly
    cat_result = run_casq("cat", hash_value, "--root", str(store))
    assert cat_result.stdout == content


def test_stdin_large_content_triggers_compression(tmp_path):
    """Test large content (≥4KB) triggers compression."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # 8KB of repeating data (should compress well)
    content = b"A" * 8192
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)

    output = result.stdout.decode().strip()
    hash_value = output.split()[0]

    # Verify content is retrievable (decompression transparent)
    cat_result = run_casq("cat", hash_value, "--root", str(store))
    assert cat_result.stdout == content
    assert len(cat_result.stdout) == 8192

    # Verify compression occurred (object file should be smaller)
    # Object path is store/objects/blake3-256/<first2hex>/<rest>
    obj_path = (
        store / "objects" / "blake3-256" / hash_value[:2] / hash_value[2:]
    )
    assert obj_path.exists()
    obj_size = obj_path.stat().st_size
    # Object includes 16-byte header + compressed payload
    # Should be significantly smaller than 8192 + 16 = 8208
    assert obj_size < 8192, f"Expected compression, got object size {obj_size}"


def test_stdin_very_large_content_triggers_chunking(tmp_path):
    """Test very large content (≥1MB) triggers chunking."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # 2MB of data (exceeds chunking threshold)
    content = b"B" * (2 * 1024 * 1024)
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)

    output = result.stdout.decode().strip()
    hash_value = output.split()[0]

    # Verify content is retrievable (chunking transparent)
    cat_result = run_casq("cat", hash_value, "--root", str(store))
    assert cat_result.stdout == content
    assert len(cat_result.stdout) == 2 * 1024 * 1024


def test_stdin_roundtrip(tmp_path):
    """Test stdin → store → cat round-trip preserves content."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Various content types
    test_contents = [
        b"simple text",
        b"multi\nline\ncontent\n",
        b"\x00binary\x00data\xff",
        b"unicode: \xc3\xa9\xc3\xa0\xc3\xbc",  # UTF-8 encoded é à ü
        b"",  # empty
    ]

    for content in test_contents:
        result = run_casq("add", "-", "--root", str(store), stdin_data=content)
        hash_value = result.stdout.decode().strip().split()[0]

        cat_result = run_casq("cat", hash_value, "--root", str(store))
        assert cat_result.stdout == content, f"Round-trip failed for {content!r}"


def test_stdin_journal_recording(tmp_path):
    """Test stdin addition is recorded in journal."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    content = b"test content for journal"
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)
    hash_value = result.stdout.decode().strip().split()[0]

    # Check journal
    journal_result = run_casq("journal", "--recent", "5", "--root", str(store))
    journal_output = journal_result.stdout.decode()

    # Should contain the hash and "(stdin)" as path
    assert hash_value in journal_output
    assert "(stdin)" in journal_output
    assert "add" in journal_output
    assert "entries=1" in journal_output


def test_stdin_orphan_detection(tmp_path):
    """Test stdin addition without ref creates orphan."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Add without ref (creates orphan)
    content = b"orphaned content"
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)
    hash_value = result.stdout.decode().strip().split()[0]

    # Should appear in orphan journal
    orphan_result = run_casq("journal", "--orphans", "--root", str(store))
    orphan_output = orphan_result.stdout.decode()

    assert hash_value in orphan_output
    assert "(stdin)" in orphan_output


def test_stdin_with_ref_not_orphan(tmp_path):
    """Test stdin addition with ref does not create orphan."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Add with ref (not orphan)
    content = b"referenced content"
    result = run_casq(
        "add", "-", "--ref-name", "my-ref", "--root", str(store), stdin_data=content
    )
    hash_value = result.stdout.decode().split()[0]

    # Should NOT appear in orphan journal
    orphan_result = run_casq("journal", "--orphans", "--root", str(store))
    orphan_output = orphan_result.stdout.decode()

    assert "No orphaned journal entries found" in orphan_output


def test_stdin_real_world_curl_simulation(tmp_path):
    """Test real-world scenario: piping curl-like output."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Simulate JSON API response (like from curl)
    json_content = json.dumps(
        {
            "status": "ok",
            "data": {"key1": "value1", "key2": [1, 2, 3]},
            "timestamp": 1737556252,
        },
        indent=2,
    ).encode("utf-8")

    result = run_casq(
        "add",
        "-",
        "--ref-name",
        "api-response@20260123",
        "--root",
        str(store),
        stdin_data=json_content,
    )

    output = result.stdout.decode()
    assert "(stdin)" in output
    assert "Created reference: api-response@20260123 ->" in output

    # Verify content is valid JSON
    hash_value = output.split()[0]
    cat_result = run_casq("cat", hash_value, "--root", str(store))
    retrieved_json = json.loads(cat_result.stdout.decode())
    assert retrieved_json["status"] == "ok"


def test_stdin_mixed_with_paths_error(tmp_path):
    """Test error when mixing stdin with filesystem paths."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("file content")

    # Try to mix stdin and file path - should fail
    result = run_casq(
        "add",
        str(test_file),
        "-",
        "--root",
        str(store),
        stdin_data=b"stdin content",
        check=False,
    )

    assert result.returncode != 0
    error_output = result.stderr.decode()
    assert "Cannot mix stdin" in error_output or "mix" in error_output.lower()


def test_stdin_multiple_stdin_error(tmp_path):
    """Test error when specifying stdin multiple times."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Try to specify stdin twice - should fail
    result = run_casq(
        "add", "-", "-", "--root", str(store), stdin_data=b"content", check=False
    )

    assert result.returncode != 0
    error_output = result.stderr.decode()
    assert "once" in error_output.lower() or "multiple" in error_output.lower()


def test_stdin_unicode_content(tmp_path):
    """Test Unicode content via stdin."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    # Unicode content (emoji, various scripts)
    content = "Hello 世界! 🌍 Здравствуй Мир".encode("utf-8")
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)

    hash_value = result.stdout.decode().strip().split()[0]

    # Verify Unicode preserved
    cat_result = run_casq("cat", hash_value, "--root", str(store))
    assert cat_result.stdout == content
    assert cat_result.stdout.decode("utf-8") == "Hello 世界! 🌍 Здравствуй Мир"


def test_stdin_hash_stability(tmp_path):
    """Test same stdin content produces same hash."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    content = b"deterministic content"

    # Add same content twice
    result1 = run_casq("add", "-", "--root", str(store), stdin_data=content)
    hash1 = result1.stdout.decode().strip().split()[0]

    result2 = run_casq("add", "-", "--root", str(store), stdin_data=content)
    hash2 = result2.stdout.decode().strip().split()[0]

    # Should produce identical hashes (deduplication)
    assert hash1 == hash2


def test_stdin_stat_shows_blob(tmp_path):
    """Test stat command shows stdin content as blob."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    content = b"content for stat test"
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)
    hash_value = result.stdout.decode().strip().split()[0]

    # Run stat
    stat_result = run_casq("stat", hash_value, "--root", str(store))
    stat_output = stat_result.stdout.decode()

    assert "Type: blob" in stat_output
    assert f"Size: {len(content)} bytes" in stat_output
    assert hash_value in stat_output


def test_stdin_ls_shows_blob(tmp_path):
    """Test ls command recognizes stdin content as blob."""
    store = tmp_path / "store"
    run_casq("init", "--root", str(store))

    content = b"content for ls test"
    result = run_casq("add", "-", "--root", str(store), stdin_data=content)
    hash_value = result.stdout.decode().strip().split()[0]

    # Run ls
    ls_result = run_casq("ls", hash_value, "--long", "--root", str(store))
    ls_output = ls_result.stdout.decode()

    assert "blob" in ls_output
    assert str(len(content)) in ls_output
