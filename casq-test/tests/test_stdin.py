"""Integration tests for stdin support in casq add command."""

import json
from fixtures import sample_files


def test_stdin_basic(cli, initialized_store):
    """Test basic stdin addition."""
    content = b"hello from stdin"
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )

    assert result.returncode == 0
    # Should output hash with "(stdin)" label
    output = result.stdout.decode().strip()
    assert "(stdin)" in output
    hash_value = output.split()[0]
    assert len(hash_value) == 64  # BLAKE3 hex length

    # Verify we can retrieve the content
    cat_result = cli.cat(hash_value, root=initialized_store)
    assert cat_result.stdout == content


def test_stdin_with_ref_name(cli, initialized_store):
    """Test stdin addition with --ref-name."""
    content = b"content with reference"
    result = cli.run(
        "add",
        "-",
        "--ref-name",
        "test-ref",
        root=initialized_store,
        input_data=content,
        binary_mode=True,
    )

    assert result.returncode == 0
    output = result.stdout.decode()
    assert "(stdin)" in output
    assert "Created reference: test-ref ->" in output

    # Verify ref was created
    refs_result = cli.refs_list(root=initialized_store)
    refs_output = refs_result.stdout
    assert "test-ref ->" in refs_output


def test_stdin_empty(cli, initialized_store):
    """Test empty stdin."""
    content = b""
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )

    assert result.returncode == 0
    output = result.stdout.decode().strip()
    assert "(stdin)" in output
    hash_value = output.split()[0]

    # Verify empty content is stored correctly
    cat_result = cli.cat(hash_value, root=initialized_store)
    assert cat_result.stdout == b""


def test_stdin_binary_data(cli, initialized_store):
    """Test binary data with null bytes."""
    content = b"\x00\x01\x02\xff\xfe\xfd"
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )

    assert result.returncode == 0
    hash_value = result.stdout.decode().strip().split()[0]

    # Verify binary content preserved exactly
    cat_result = cli.cat(hash_value, root=initialized_store)
    assert cat_result.stdout == content


def test_stdin_large_content_triggers_compression(cli, initialized_store):
    """Test large content (≥4KB) triggers compression."""
    # 8KB of repeating data (should compress well)
    content = b"A" * 8192
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )

    assert result.returncode == 0
    hash_value = result.stdout.decode().strip().split()[0]

    # Verify content is retrievable (decompression transparent)
    cat_result = cli.cat(hash_value, root=initialized_store)
    assert cat_result.stdout == content
    assert len(cat_result.stdout) == 8192

    # Verify compression occurred (object file should be smaller)
    obj_path = (
        initialized_store / "objects" / "blake3-256" / hash_value[:2] / hash_value[2:]
    )
    assert obj_path.exists()
    obj_size = obj_path.stat().st_size
    # Object includes 16-byte header + compressed payload
    # Should be significantly smaller than 8192 + 16 = 8208
    assert obj_size < 8192, f"Expected compression, got object size {obj_size}"


def test_stdin_very_large_content_triggers_chunking(cli, initialized_store):
    """Test very large content (≥1MB) triggers chunking."""
    # 2MB of data (exceeds chunking threshold)
    content = b"B" * (2 * 1024 * 1024)
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )

    assert result.returncode == 0
    hash_value = result.stdout.decode().strip().split()[0]

    # Verify content is retrievable (chunking transparent)
    cat_result = cli.cat(hash_value, root=initialized_store)
    assert cat_result.stdout == content
    assert len(cat_result.stdout) == 2 * 1024 * 1024


def test_stdin_roundtrip(cli, initialized_store):
    """Test stdin → store → cat round-trip preserves content."""
    test_contents = [
        b"simple text",
        b"multi\nline\ncontent\n",
        b"\x00binary\x00data\xff",
        b"unicode: \xc3\xa9\xc3\xa0\xc3\xbc",  # UTF-8 encoded é à ü
        b"",  # empty
    ]

    for content in test_contents:
        result = cli.run(
            "add", "-", root=initialized_store, input_data=content, binary_mode=True
        )
        hash_value = result.stdout.decode().strip().split()[0]

        cat_result = cli.cat(hash_value, root=initialized_store)
        assert cat_result.stdout == content, f"Round-trip failed for {content!r}"


def test_stdin_journal_recording(cli, initialized_store):
    """Test stdin addition is recorded in journal."""
    content = b"test content for journal"
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )
    hash_value = result.stdout.decode().strip().split()[0]

    # Check journal
    journal_result = cli.run("journal", "--recent", "5", root=initialized_store)
    journal_output = journal_result.stdout

    # Should contain the hash and "(stdin)" as path
    assert hash_value in journal_output
    assert "(stdin)" in journal_output
    assert "add" in journal_output
    assert "entries=1" in journal_output


def test_stdin_orphan_detection(cli, initialized_store):
    """Test stdin addition without ref creates orphan."""
    content = b"orphaned content"
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )
    hash_value = result.stdout.decode().strip().split()[0]

    # Should appear in orphan journal
    orphan_result = cli.run("journal", "--orphans", root=initialized_store)
    orphan_output = orphan_result.stdout

    assert hash_value in orphan_output
    assert "(stdin)" in orphan_output


def test_stdin_with_ref_not_orphan(cli, initialized_store):
    """Test stdin addition with ref does not create orphan."""
    content = b"referenced content"
    result = cli.run(
        "add",
        "-",
        "--ref-name",
        "my-ref",
        root=initialized_store,
        input_data=content,
        binary_mode=True,
    )
    hash_value = result.stdout.decode().split()[0]

    assert hash_value != ""

    # Should NOT appear in orphan journal
    orphan_result = cli.run("journal", "--orphans", root=initialized_store)
    orphan_output = orphan_result.stdout

    assert "No orphaned journal entries found" in orphan_output


def test_stdin_real_world_curl_simulation(cli, initialized_store):
    """Test real-world scenario: piping curl-like output."""
    # Simulate JSON API response (like from curl)
    json_content = json.dumps(
        {
            "status": "ok",
            "data": {"key1": "value1", "key2": [1, 2, 3]},
            "timestamp": 1737556252,
        },
        indent=2,
    ).encode("utf-8")

    result = cli.run(
        "add",
        "-",
        "--ref-name",
        "api-response@20260123",
        root=initialized_store,
        input_data=json_content,
        binary_mode=True,
    )

    assert result.returncode == 0
    output = result.stdout.decode()
    assert "(stdin)" in output
    assert "Created reference: api-response@20260123 ->" in output

    # Verify content is valid JSON
    hash_value = output.split()[0]
    cat_result = cli.cat(hash_value, root=initialized_store)
    retrieved_json = json.loads(cat_result.stdout.decode())
    assert retrieved_json["status"] == "ok"


def test_stdin_mixed_with_paths_error(cli, initialized_store, workspace):
    """Test error when mixing stdin with filesystem paths."""
    # Create a test file
    test_file = sample_files.create_sample_file(workspace / "test.txt", "file content")

    # Try to mix stdin and file path - should fail
    result = cli.run(
        "add",
        str(test_file),
        "-",
        root=initialized_store,
        input_data=b"stdin content",
        binary_mode=True,
        expect_success=False,
    )

    assert result.returncode != 0
    error_output = result.stderr.decode()
    assert "Cannot mix stdin" in error_output or "mix" in error_output.lower()


def test_stdin_multiple_stdin_error(cli, initialized_store):
    """Test error when specifying stdin multiple times."""
    # Try to specify stdin twice - should fail
    result = cli.run(
        "add",
        "-",
        "-",
        root=initialized_store,
        input_data=b"content",
        binary_mode=True,
        expect_success=False,
    )

    assert result.returncode != 0
    error_output = result.stderr.decode()
    assert "once" in error_output.lower() or "multiple" in error_output.lower()


def test_stdin_unicode_content(cli, initialized_store):
    """Test Unicode content via stdin."""
    # Unicode content (emoji, various scripts)
    content = "Hello 世界! 🌍 Здравствуй Мир".encode("utf-8")
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )

    assert result.returncode == 0
    hash_value = result.stdout.decode().strip().split()[0]

    # Verify Unicode preserved
    cat_result = cli.cat(hash_value, root=initialized_store)
    assert cat_result.stdout == content
    assert cat_result.stdout.decode("utf-8") == "Hello 世界! 🌍 Здравствуй Мир"


def test_stdin_hash_stability(cli, initialized_store):
    """Test same stdin content produces same hash."""
    content = b"deterministic content"

    # Add same content twice
    result1 = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )
    hash1 = result1.stdout.decode().strip().split()[0]

    result2 = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )
    hash2 = result2.stdout.decode().strip().split()[0]

    # Should produce identical hashes (deduplication)
    assert hash1 == hash2


def test_stdin_stat_shows_blob(cli, initialized_store):
    """Test stat command shows stdin content as blob."""
    content = b"content for stat test"
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )
    hash_value = result.stdout.decode().strip().split()[0]

    # Run stat
    stat_result = cli.stat(hash_value, root=initialized_store)
    stat_output = stat_result.stdout

    assert "Type: blob" in stat_output
    assert f"Size: {len(content)} bytes" in stat_output
    assert hash_value in stat_output


def test_stdin_ls_shows_blob(cli, initialized_store):
    """Test ls command recognizes stdin content as blob."""
    content = b"content for ls test"
    result = cli.run(
        "add", "-", root=initialized_store, input_data=content, binary_mode=True
    )
    hash_value = result.stdout.decode().strip().split()[0]

    # Run ls
    ls_result = cli.ls(hash_value, root=initialized_store, long_format=True)
    ls_output = ls_result.stdout

    assert "blob" in ls_output
    assert str(len(content)) in ls_output
