"""Tests for hash determinism and stability."""

from fixtures import sample_files


def test_same_file_same_hash_determinism(cli, initialized_store, workspace):
    """Test that same file content always produces same hash."""
    content = "deterministic test content\n"

    # Add same content multiple times
    hashes = []
    for i in range(5):
        file = sample_files.create_sample_file(workspace / f"test{i}.txt", content)
        result = cli.add(file, root=initialized_store)
        hashes.append(result.stdout.strip().split()[0])

    # All hashes should be identical
    assert len(set(hashes)) == 1


def test_same_directory_same_hash(cli, initialized_store, workspace):
    """Test that identical directory structures produce same hash."""
    structure = {
        "file1.txt": "content 1",
        "file2.txt": "content 2",
        "subdir": {
            "nested.txt": "nested content",
        },
    }

    # Create same structure twice
    tree1 = sample_files.create_directory_tree(workspace / "tree1", structure)
    tree2 = sample_files.create_directory_tree(workspace / "tree2", structure)

    hash1 = cli.add(tree1, root=initialized_store).stdout.strip().split()[0]
    hash2 = cli.add(tree2, root=initialized_store).stdout.strip().split()[0]

    assert hash1 == hash2


def test_tree_entry_order_independence(cli, initialized_store, workspace):
    """Test that tree entries are sorted, making hash order-independent."""
    # Create files in different orders
    tree1 = workspace / "tree1"
    tree1.mkdir()
    sample_files.create_sample_file(tree1 / "a.txt", "content a")
    sample_files.create_sample_file(tree1 / "z.txt", "content z")
    sample_files.create_sample_file(tree1 / "m.txt", "content m")

    tree2 = workspace / "tree2"
    tree2.mkdir()
    sample_files.create_sample_file(tree2 / "z.txt", "content z")
    sample_files.create_sample_file(tree2 / "m.txt", "content m")
    sample_files.create_sample_file(tree2 / "a.txt", "content a")

    hash1 = cli.add(tree1, root=initialized_store).stdout.strip().split()[0]
    hash2 = cli.add(tree2, root=initialized_store).stdout.strip().split()[0]

    # Should have same hash despite creation order
    assert hash1 == hash2


def test_hash_format_validation(cli, initialized_store, sample_file):
    """Test that hash output is always valid 64-char hex."""
    result = cli.add(sample_file, root=initialized_store)
    hash_val = result.stdout.strip().split()[0]

    # Should be 64 hex characters (BLAKE3 256-bit)
    assert len(hash_val) == 64
    # Should be valid hex
    int(hash_val, 16)
    # Should be lowercase hex
    assert hash_val == hash_val.lower()


def test_empty_file_consistent_hash(cli, initialized_store, workspace):
    """Test that all empty files produce the same hash."""
    empty_hashes = []

    for i in range(5):
        empty = sample_files.create_empty_file(workspace / f"empty{i}.txt")
        result = cli.add(empty, root=initialized_store)
        empty_hashes.append(result.stdout.strip().split()[0])

    # All empty files should have identical hash
    assert len(set(empty_hashes)) == 1


def test_binary_content_hash_stability(cli, initialized_store, workspace):
    """Test hash stability for binary content."""
    pattern = b"\xde\xad\xbe\xef"
    size = 1024

    hashes = []
    for i in range(3):
        binary = sample_files.create_binary_file(
            workspace / f"binary{i}.dat", size=size, pattern=pattern
        )
        result = cli.add(binary, root=initialized_store)
        hashes.append(result.stdout.strip().split()[0])

    # All should produce same hash
    assert len(set(hashes)) == 1


def test_newline_style_affects_hash(cli, initialized_store, workspace):
    """Test that different newline styles produce different hashes."""
    # Different newline styles should produce different hashes
    # because content is different at byte level

    unix_file = sample_files.create_sample_file(
        workspace / "unix.txt", "line1\nline2\n"
    )
    windows_file = sample_files.create_sample_file(
        workspace / "windows.txt", "line1\r\nline2\r\n"
    )

    hash_unix = cli.add(unix_file, root=initialized_store).stdout.strip().split()[0]
    hash_windows = (
        cli.add(windows_file, root=initialized_store).stdout.strip().split()[0]
    )

    # Different content = different hash
    assert hash_unix != hash_windows


def test_repeated_add_same_hash(cli, initialized_store, workspace):
    """Test that adding same file multiple times always returns same hash."""
    test_file = sample_files.create_sample_file(
        workspace / "test.txt", "consistent content"
    )

    hashes = []
    for _ in range(10):
        result = cli.add(test_file, root=initialized_store)
        hashes.append(result.stdout.strip().split()[0])

    # All adds should return identical hash
    assert len(set(hashes)) == 1
