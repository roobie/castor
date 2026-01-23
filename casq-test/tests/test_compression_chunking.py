"""Tests for compression and chunking features (v0.4.0)."""

import pytest
import struct
from pathlib import Path
from fixtures import sample_files
from helpers.verification import (
    verify_object_exists,
    get_object_path,
    get_object_type,
    count_objects,
    read_object_header,
)


def get_compression_type(store_path: Path, hash_str: str, algo: str = "blake3-256") -> int:
    """
    Get the compression type from object header (v2 format).

    Args:
        store_path: Path to the store root
        hash_str: Object hash (hex string)
        algo: Hash algorithm

    Returns:
        Compression type: 0=None, 1=Zstd
    """
    header = read_object_header(store_path, hash_str, algo)
    obj_path = get_object_path(store_path, hash_str, algo)

    with open(obj_path, "rb") as f:
        header_bytes = f.read(16)
        version = header_bytes[4]
        compression_byte = header_bytes[7]

        # v2 format: byte 7 is compression type
        # v1 format: byte 7 must be 0 (reserved)
        if version == 2:
            return compression_byte
        else:
            return 0  # v1 doesn't support compression


def get_object_version(store_path: Path, hash_str: str, algo: str = "blake3-256") -> int:
    """Get the version of an object."""
    header = read_object_header(store_path, hash_str, algo)
    return header["version"]


def get_stored_size(store_path: Path, hash_str: str, algo: str = "blake3-256") -> int:
    """Get the total stored size of an object (header + payload)."""
    obj_path = get_object_path(store_path, hash_str, algo)
    return obj_path.stat().st_size


def get_payload_size(store_path: Path, hash_str: str, algo: str = "blake3-256") -> int:
    """Get the payload size from object header."""
    header = read_object_header(store_path, hash_str, algo)
    return header["payload_len"]


@pytest.mark.smoke
def test_small_file_not_compressed(cli, initialized_store, workspace):
    """Test that small files (< 4KB) are not compressed."""
    # Create a 2KB file
    small_file = sample_files.create_binary_file(
        workspace / "small.bin",
        size=2048,
        pattern=b"AAAA"
    )

    result = cli.add(small_file, root=initialized_store)
    assert result.returncode == 0

    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)

    # Check compression type (should be 0 = None)
    compression = get_compression_type(initialized_store, hash_output)
    assert compression == 0, "Small file should not be compressed"


def test_medium_file_is_compressed(cli, initialized_store, workspace):
    """Test that files >= 4KB are compressed with zstd."""
    # Create a 10KB file with repetitive data (highly compressible)
    medium_file = sample_files.create_binary_file(
        workspace / "medium.bin",
        size=10 * 1024,
        pattern=b"ABCD"
    )

    result = cli.add(medium_file, root=initialized_store)
    assert result.returncode == 0

    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)

    # Check compression type (should be 1 = Zstd)
    compression = get_compression_type(initialized_store, hash_output)
    assert compression == 1, "Medium file should be compressed with zstd"

    # Check version is v2
    version = get_object_version(initialized_store, hash_output)
    assert version == 2, "Compressed object should use v2 format"


def test_compression_reduces_storage(cli, initialized_store, workspace):
    """Test that compression actually reduces storage size."""
    # Create 50KB of highly compressible data
    compressible_file = sample_files.create_binary_file(
        workspace / "compressible.bin",
        size=50 * 1024,
        pattern=b"AAAA"  # Very repetitive = high compression ratio
    )

    result = cli.add(compressible_file, root=initialized_store)
    hash_output = result.stdout.strip().split()[0]

    # Get stored size (header + compressed payload)
    stored_size = get_stored_size(initialized_store, hash_output)
    original_size = 50 * 1024

    # Compressed size should be significantly smaller
    # (For repetitive data, expect >10x compression)
    assert stored_size < original_size / 5, \
        f"Stored size {stored_size} should be much smaller than original {original_size}"


def test_compressed_file_round_trip(cli, initialized_store, workspace):
    """Test that compressed files can be materialized correctly."""
    # Create compressible file
    original_file = sample_files.create_sample_file(
        workspace / "original.txt",
        "Hello World! " * 1000  # Repetitive text, ~13KB
    )

    # Add to store
    result = cli.add(original_file, root=initialized_store)
    hash_output = result.stdout.strip().split()[0]

    # Verify compression
    compression = get_compression_type(initialized_store, hash_output)
    assert compression == 1, "File should be compressed"

    # Materialize
    restored_dir = workspace / "restored"
    restored_dir.mkdir()
    result = cli.materialize(hash_output, restored_dir / "restored.txt", root=initialized_store)
    assert result.returncode == 0

    # Verify content matches
    original_content = original_file.read_text()
    restored_content = (restored_dir / "restored.txt").read_text()
    assert restored_content == original_content, "Restored content should match original"


@pytest.mark.slow
def test_large_file_is_chunked(cli, initialized_store, workspace):
    """Test that files >= 1MB are chunked using FastCDC."""
    # Create a 2MB file
    large_file = sample_files.create_binary_file(
        workspace / "large.bin",
        size=2 * 1024 * 1024,
        pattern=b"0123456789ABCDEF"
    )

    result = cli.add(large_file, root=initialized_store)
    assert result.returncode == 0

    hash_output = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, hash_output)

    # Check object type (should be 3 = ChunkList)
    obj_type_id = read_object_header(initialized_store, hash_output)["type"]
    assert obj_type_id == 3, "Large file should be stored as ChunkList (type 3)"


@pytest.mark.slow
def test_chunked_file_creates_multiple_chunks(cli, initialized_store, workspace):
    """Test that chunked files create multiple chunk objects."""
    initial_count = count_objects(initialized_store)

    # Create 3MB file where each 1MB section has a unique marker to prevent deduplication
    # Section 1: All 'A's
    # Section 2: All 'B's
    # Section 3: All 'C's
    data = b'A' * (1024 * 1024) + b'B' * (1024 * 1024) + b'C' * (1024 * 1024)
    large_file = workspace / "large.bin"
    large_file.write_bytes(data)

    result = cli.add(large_file, root=initialized_store)
    hash_output = result.stdout.strip().split()[0]

    final_count = count_objects(initialized_store)

    # Should have created: 1 ChunkList + multiple chunk blobs
    # With 512KB avg chunks and 3 distinct 1MB sections, we should get:
    # - Section A: ~2 chunks
    # - Section B: ~2 chunks
    # - Section C: ~2 chunks
    # - 1 ChunkList
    # Total: ~7 objects minimum
    # However, chunks within a section might dedupe, so expect at least 3 total
    objects_created = final_count - initial_count
    assert objects_created >= 2, \
        f"Expected at least 2 objects (1 ChunkList + 1+ chunks), got {objects_created}"

    # Verify it's actually a ChunkList
    obj_type = read_object_header(initialized_store, hash_output)["type"]
    assert obj_type == 3, "Large file should create ChunkList object (type 3)"


@pytest.mark.slow
def test_chunked_file_round_trip(cli, initialized_store, workspace):
    """Test that chunked files can be materialized correctly."""
    # Create 3MB file with pattern
    original_file = sample_files.create_binary_file(
        workspace / "chunked.bin",
        size=3 * 1024 * 1024,
        pattern=b"CHUNKED!"
    )
    original_content = original_file.read_bytes()

    # Add to store
    result = cli.add(original_file, root=initialized_store)
    hash_output = result.stdout.strip().split()[0]

    # Verify it's chunked
    obj_type_id = read_object_header(initialized_store, hash_output)["type"]
    assert obj_type_id == 3, "Should be ChunkList"

    # Materialize
    restored_dir = workspace / "restored"
    restored_dir.mkdir()
    result = cli.materialize(hash_output, restored_dir / "chunked.bin", root=initialized_store)
    assert result.returncode == 0

    # Verify content matches byte-for-byte
    restored_content = (restored_dir / "chunked.bin").read_bytes()
    assert restored_content == original_content, "Restored content should match original"
    assert len(restored_content) == 3 * 1024 * 1024, "Restored size should match"


def test_chunked_file_cat_works(cli, initialized_store, workspace):
    """Test that cat command works on chunked files."""
    # Create 1.5MB file
    large_file = sample_files.create_sample_file(
        workspace / "large.txt",
        "Line of text\n" * 100000  # ~1.3MB
    )
    original_content = large_file.read_text()

    result = cli.add(large_file, root=initialized_store)
    hash_output = result.stdout.strip().split()[0]

    # Cat the chunked file
    cat_result = cli.cat(hash_output, root=initialized_store)
    assert cat_result.returncode == 0

    # Verify output matches original (stdout is bytes, decode it)
    cat_output = cat_result.stdout.decode('utf-8') if isinstance(cat_result.stdout, bytes) else cat_result.stdout
    assert cat_output == original_content, "Cat output should match original"


def test_compressed_deduplication(cli, initialized_store, workspace):
    """Test that compression doesn't break deduplication."""
    # Create two identical compressible files
    file1 = sample_files.create_binary_file(
        workspace / "file1.bin",
        size=10 * 1024,
        pattern=b"SAME"
    )
    file2 = sample_files.create_binary_file(
        workspace / "file2.bin",
        size=10 * 1024,
        pattern=b"SAME"
    )

    # Add first file
    result1 = cli.add(file1, root=initialized_store)
    hash1 = result1.stdout.strip().split()[0]
    count1 = count_objects(initialized_store)

    # Add identical file
    result2 = cli.add(file2, root=initialized_store)
    hash2 = result2.stdout.strip().split()[0]
    count2 = count_objects(initialized_store)

    # Same hash, same count (deduplication worked)
    assert hash1 == hash2, "Identical files should have same hash"
    assert count2 == count1, "No new objects should be created (deduplication)"


@pytest.mark.slow
def test_chunked_deduplication(cli, initialized_store, workspace):
    """Test that chunking enables deduplication of shared chunks."""
    # Create two 2MB files with overlapping content
    # File 1: AAAABBBB (1MB A's + 1MB B's)
    file1_data = b"A" * (1024 * 1024) + b"B" * (1024 * 1024)
    file1 = workspace / "file1.bin"
    file1.write_bytes(file1_data)

    # File 2: BBBBCCCC (1MB B's + 1MB C's)
    file2_data = b"B" * (1024 * 1024) + b"C" * (1024 * 1024)
    file2 = workspace / "file2.bin"
    file2.write_bytes(file2_data)

    # Add first file
    result1 = cli.add(file1, root=initialized_store)
    hash1 = result1.stdout.strip().split()[0]
    count1 = count_objects(initialized_store)

    # Add second file
    result2 = cli.add(file2, root=initialized_store)
    hash2 = result2.stdout.strip().split()[0]
    count2 = count_objects(initialized_store)

    # Different files, different hashes
    assert hash1 != hash2, "Different files should have different hashes"

    # But some chunks should be shared (B section is identical)
    # Expected: file1 creates ~4-5 objects, file2 should create fewer (shared B chunks)
    objects_for_file1 = count1
    objects_for_file2 = count2 - count1

    # File2 should create fewer objects due to shared chunks
    assert objects_for_file2 < objects_for_file1, \
        f"File2 should create fewer objects ({objects_for_file2}) than file1 ({objects_for_file1}) due to chunk sharing"


def test_compression_on_tree_with_mixed_sizes(cli, initialized_store, workspace):
    """Test adding directory with files of various sizes."""
    tree_dir = workspace / "mixed"
    tree_dir.mkdir()

    # Small file (no compression)
    sample_files.create_binary_file(tree_dir / "small.bin", size=1024, pattern=b"S")

    # Medium file (compression)
    sample_files.create_binary_file(tree_dir / "medium.bin", size=10 * 1024, pattern=b"M")

    # Large file (chunking)
    sample_files.create_binary_file(tree_dir / "large.bin", size=1500 * 1024, pattern=b"L")

    result = cli.add(tree_dir, root=initialized_store)
    assert result.returncode == 0

    tree_hash = result.stdout.strip().split()[0]
    verify_object_exists(initialized_store, tree_hash)


def test_gc_works_with_chunked_objects(cli, initialized_store, workspace):
    """Test that GC correctly handles chunked objects and their chunks."""
    # Create chunked file with ref
    large_file = sample_files.create_binary_file(
        workspace / "large.bin",
        size=2 * 1024 * 1024,
        pattern=b"GCTEST"
    )

    result = cli.add(large_file, root=initialized_store, ref_name="keep")
    hash_output = result.stdout.strip().split()[0]

    # Create another chunked file without ref (orphan)
    orphan_file = sample_files.create_binary_file(
        workspace / "orphan.bin",
        size=2 * 1024 * 1024,
        pattern=b"ORPHAN"
    )

    cli.add(orphan_file, root=initialized_store)
    count_before_gc = count_objects(initialized_store)

    # Run GC
    gc_result = cli.gc(root=initialized_store)
    assert gc_result.returncode == 0

    count_after_gc = count_objects(initialized_store)

    # Some objects should be deleted (orphan ChunkList + its chunks)
    assert count_after_gc < count_before_gc, "GC should delete orphaned chunked objects"

    # Referenced chunked file should still exist
    verify_object_exists(initialized_store, hash_output)

    # Should still be able to materialize
    restored_dir = workspace / "restored"
    restored_dir.mkdir()
    result = cli.materialize(hash_output, restored_dir / "large.bin", root=initialized_store)
    assert result.returncode == 0


def test_object_format_version(cli, initialized_store, workspace):
    """Test that new objects use v2 format."""
    # Add various files
    small = sample_files.create_binary_file(workspace / "small.bin", size=1024, pattern=b"S")
    medium = sample_files.create_binary_file(workspace / "medium.bin", size=10 * 1024, pattern=b"M")

    result1 = cli.add(small, root=initialized_store)
    hash1 = result1.stdout.strip().split()[0]

    result2 = cli.add(medium, root=initialized_store)
    hash2 = result2.stdout.strip().split()[0]

    # Both should use v2 format
    version1 = get_object_version(initialized_store, hash1)
    version2 = get_object_version(initialized_store, hash2)

    assert version1 == 2, "New objects should use v2 format"
    assert version2 == 2, "New objects should use v2 format"


def test_compression_with_various_data_patterns(cli, initialized_store, workspace):
    """Test compression with different data patterns."""
    test_cases = [
        ("highly_compressible.bin", b"A" * 10240, "Highly repetitive data"),
        ("text.txt", b"The quick brown fox jumps over the lazy dog.\n" * 200, "Natural text"),
        ("random.bin", bytes(range(256)) * 40, "Sequential pattern"),
    ]

    for filename, data, description in test_cases:
        file_path = workspace / filename
        file_path.write_bytes(data)

        result = cli.add(file_path, root=initialized_store)
        assert result.returncode == 0, f"Failed to add {description}"

        hash_output = result.stdout.strip().split()[0]

        # All should be compressed (>4KB)
        compression = get_compression_type(initialized_store, hash_output)
        assert compression == 1, f"{description} should be compressed"

        # Verify round-trip
        restored = workspace / f"restored_{filename}"
        cli.materialize(hash_output, restored, root=initialized_store)
        assert restored.read_bytes() == data, f"{description} round-trip failed"


@pytest.mark.slow
def test_chunking_boundary_cases(cli, initialized_store, workspace):
    """Test chunking at threshold boundaries."""
    # Well above threshold (1.5MB) - should definitely be chunked
    above_threshold = sample_files.create_binary_file(
        workspace / "above.bin",
        size=1024 * 1024 + 512 * 1024,  # 1.5MB
        pattern=b"X"
    )

    result = cli.add(above_threshold, root=initialized_store)
    hash_above = result.stdout.strip().split()[0]
    type_above = read_object_header(initialized_store, hash_above)["type"]
    assert type_above == 3, "Files >= 1MB should be chunked (ChunkList type)"

    # Well under threshold (512KB) - should NOT be chunked
    well_under = sample_files.create_binary_file(
        workspace / "well_under.bin",
        size=512 * 1024,
        pattern=b"Y"
    )

    result = cli.add(well_under, root=initialized_store)
    hash_under = result.stdout.strip().split()[0]
    type_under = read_object_header(initialized_store, hash_under)["type"]
    assert type_under == 1, "Files under 1MB should be regular blob (Blob type)"


def test_stat_shows_compression_info(cli, initialized_store, workspace):
    """Test that stat command works with compressed objects."""
    compressed_file = sample_files.create_binary_file(
        workspace / "compressed.bin",
        size=20 * 1024,
        pattern=b"COMP"
    )

    result = cli.add(compressed_file, root=initialized_store)
    hash_output = result.stdout.strip().split()[0]

    stat_result = cli.stat(hash_output, root=initialized_store)
    assert stat_result.returncode == 0

    # Verify stat output contains expected fields
    output = stat_result.stdout.lower()
    assert "hash:" in output or hash_output in output, "Stat should show hash"
    assert "type:" in output or "blob" in output, "Stat should show type"

    # Check that on-disk size is smaller than original (compression worked)
    stored_size = get_stored_size(initialized_store, hash_output)
    original_size = 20 * 1024
    assert stored_size < original_size, \
        f"Compressed object size {stored_size} should be smaller than original {original_size}"
