"""Tests for 'castor cat' command."""

import pytest
from fixtures import sample_files
from helpers.verification import get_object_type


@pytest.mark.smoke
def test_cat_text_blob(cli, initialized_store, workspace):
    """Test catting a text blob to stdout."""
    content = "Hello, world!\n"
    text_file = sample_files.create_sample_file(workspace / "test.txt", content)

    add_result = cli.add(text_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.returncode == 0
    assert cat_result.stdout == content.encode('utf-8')


def test_cat_binary_blob(cli, initialized_store, workspace):
    """Test catting a binary blob."""
    binary = sample_files.create_binary_file(
        workspace / "binary.dat",
        size=100,
        pattern=b"\xDE\xAD\xBE\xEF"
    )

    add_result = cli.add(binary, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.returncode == 0
    # Binary output should match original (cat now returns bytes)
    assert cat_result.stdout == binary.read_bytes()


def test_cat_empty_blob(cli, initialized_store, workspace):
    """Test catting an empty blob."""
    empty = sample_files.create_empty_file(workspace / "empty.txt")

    add_result = cli.add(empty, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.returncode == 0
    assert cat_result.stdout == b""


def test_cat_large_blob(cli, initialized_store, workspace):
    """Test catting a large blob."""
    content = "x" * (1024 * 100)  # 100KB
    large_file = sample_files.create_sample_file(workspace / "large.txt", content)

    add_result = cli.add(large_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.returncode == 0
    assert len(cat_result.stdout) == len(content)


def test_cat_invalid_hash_format(cli, initialized_store):
    """Test cat with invalid hash format."""
    result = cli.cat("invalid_hash", root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_cat_nonexistent_hash(cli, initialized_store):
    """Test cat with non-existent hash."""
    fake_hash = "0" * 64
    result = cli.cat(fake_hash, root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0


def test_cat_tree_hash_error(cli, initialized_store, sample_tree):
    """Test that cat fails when given a tree hash (not a blob)."""
    add_result = cli.add(sample_tree, root=initialized_store)
    tree_hash = add_result.stdout.strip().split()[0]

    # Verify it's actually a tree
    assert get_object_type(initialized_store, tree_hash) == "tree"

    # Cat should fail
    result = cli.cat(tree_hash, root=initialized_store, expect_success=False)

    assert result.returncode != 0
    stderr_text = result.stderr.decode('utf-8').lower()
    assert "tree" in stderr_text or "blob" in stderr_text


def test_cat_content_verification(cli, initialized_store, workspace):
    """Test that cat output exactly matches original content."""
    original_content = "Line 1\nLine 2\nLine 3\n"
    test_file = sample_files.create_sample_file(workspace / "content.txt", original_content)

    add_result = cli.add(test_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.stdout == original_content.encode('utf-8')


def test_cat_binary_data_preservation(cli, initialized_store, workspace):
    """Test that binary data is preserved correctly."""
    binary_content = bytes(range(256))
    binary_file = workspace / "binary.dat"
    binary_file.write_bytes(binary_content)

    add_result = cli.add(binary_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    # Output should be binary data (cat now returns bytes)
    assert cat_result.returncode == 0
    assert cat_result.stdout == binary_content


def test_cat_multiline_text(cli, initialized_store, workspace):
    """Test catting multiline text file."""
    multiline = "First line\nSecond line\nThird line\nFourth line\n"
    text_file = sample_files.create_sample_file(workspace / "multiline.txt", multiline)

    add_result = cli.add(text_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.stdout == multiline.encode('utf-8')


def test_cat_file_with_special_characters(cli, initialized_store, workspace):
    """Test catting file with special characters."""
    special = "Special: !@#$%^&*()_+-=[]{}|;:',.<>?/~`\n"
    special_file = sample_files.create_sample_file(workspace / "special.txt", special)

    add_result = cli.add(special_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.stdout == special.encode('utf-8')


def test_cat_unicode_content(cli, initialized_store, workspace):
    """Test catting file with unicode content."""
    unicode_content = "Hello 世界 🌍\nCafé ☕\n"
    unicode_file = sample_files.create_sample_file(workspace / "unicode.txt", unicode_content)

    add_result = cli.add(unicode_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.returncode == 0
    assert cat_result.stdout == unicode_content.encode('utf-8')


def test_cat_file_with_no_trailing_newline(cli, initialized_store, workspace):
    """Test catting file without trailing newline."""
    no_newline = "No trailing newline"
    test_file = sample_files.create_sample_file(workspace / "no_newline.txt", no_newline)

    add_result = cli.add(test_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.stdout == no_newline.encode('utf-8')


def test_cat_file_with_null_bytes(cli, initialized_store, workspace):
    """Test catting file containing null bytes."""
    null_content = b"before\x00null\x00bytes\x00after"
    null_file = workspace / "null.dat"
    null_file.write_bytes(null_content)

    add_result = cli.add(null_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.returncode == 0


def test_cat_same_content_different_files(cli, initialized_store, workspace):
    """Test that catting deduplicated content works."""
    content = "Same content\n"
    file1 = sample_files.create_sample_file(workspace / "file1.txt", content)
    file2 = sample_files.create_sample_file(workspace / "file2.txt", content)

    add1 = cli.add(file1, root=initialized_store)
    hash1 = add1.stdout.strip().split()[0]

    add2 = cli.add(file2, root=initialized_store)
    hash2 = add2.stdout.strip().split()[0]

    # Should be same hash (deduplicated)
    assert hash1 == hash2

    # Cat should work
    cat_result = cli.cat(hash1, root=initialized_store)
    assert cat_result.stdout == content.encode('utf-8')


def test_cat_outputs_to_stdout_not_stderr(cli, initialized_store, workspace):
    """Test that cat outputs content to stdout, not stderr."""
    content = "stdout test\n"
    test_file = sample_files.create_sample_file(workspace / "stdout.txt", content)

    add_result = cli.add(test_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert content.encode('utf-8') in cat_result.stdout
    # Stderr should be empty or only contain informational messages
    assert cat_result.stderr == b"" or b"error" not in cat_result.stderr.lower()


def test_cat_file_with_mixed_newlines(cli, initialized_store, workspace):
    """Test catting file with mixed newline styles."""
    # Use bytes to ensure exact preservation of \r\n and \r
    mixed = b"unix\nwindows\r\nmac\rend"
    mixed_file = workspace / "mixed.txt"
    mixed_file.write_bytes(mixed)

    add_result = cli.add(mixed_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    cat_result = cli.cat(file_hash, root=initialized_store)

    assert cat_result.returncode == 0
    # Content should be preserved as-is (cat now returns bytes)
    assert cat_result.stdout == mixed


def test_cat_multiple_times_same_hash(cli, initialized_store, workspace):
    """Test catting the same hash multiple times."""
    content = "Multiple cat test\n"
    test_file = sample_files.create_sample_file(workspace / "test.txt", content)

    add_result = cli.add(test_file, root=initialized_store)
    file_hash = add_result.stdout.strip().split()[0]

    # Cat multiple times
    result1 = cli.cat(file_hash, root=initialized_store)
    result2 = cli.cat(file_hash, root=initialized_store)
    result3 = cli.cat(file_hash, root=initialized_store)

    assert result1.stdout == result2.stdout == result3.stdout == content.encode('utf-8')
