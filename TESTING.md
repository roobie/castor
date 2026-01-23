# Testing Guide for casq v0.4.0

## Quick Start

```bash
# Run all Rust unit tests
cargo test

# Run all Rust tests with output
cargo test -- --nocapture

# Run only compression/chunking tests
cargo test -p casq_core chunking
cargo test -p casq_core compression
```

## Python Integration Tests

The Python test suite includes 25+ new tests for compression and chunking features.

### Prerequisites

```bash
# Build the debug binary (required by Python tests)
cargo build

# Verify binary exists
ls -l target/debug/casq
```

### Running Python Tests

**Note:** The Python test environment may need network access to install dependencies. If network is unavailable, tests can be run manually after the environment is set up.

```bash
cd casq-test

# Run all tests (when network available)
uv run pytest

# Run only compression/chunking tests
uv run pytest tests/test_compression_chunking.py -v

# Run specific test
uv run pytest tests/test_compression_chunking.py::test_medium_file_is_compressed -v

# Run smoke tests only (fast validation)
uv run pytest -m smoke

# Run slow tests (large file operations)
uv run pytest -m slow
```

## Test Coverage

### Rust Unit Tests (92 tests)

**Module breakdown:**
- `chunking`: 5 tests (basic, boundaries, deterministic, small files, empty files)
- `object`: 15 tests (header encoding, type conversions, compression types, v1/v2 compat)
- `store`: 50+ tests (put/get, trees, materialization, GC, deduplication)
- `hash`: 8 tests (hashing, encoding, ordering)
- `tree`: 5 tests (encoding, ordering, entries)
- `gc`: 8 tests (reachability, orphan detection)

### Python Integration Tests (25+ tests)

**New tests in `test_compression_chunking.py`:**

1. **Compression Tests:**
   - `test_small_file_not_compressed` - Files <4KB not compressed
   - `test_medium_file_is_compressed` - Files ≥4KB compressed with zstd
   - `test_compression_reduces_storage` - Verify storage savings
   - `test_compressed_file_round_trip` - Add → materialize integrity
   - `test_compression_with_various_data_patterns` - Different data types
   - `test_compressed_deduplication` - Dedup still works

2. **Chunking Tests:**
   - `test_large_file_is_chunked` - Files ≥1MB chunked
   - `test_chunked_file_creates_multiple_chunks` - Verify chunk count
   - `test_chunked_file_round_trip` - Add → materialize large files
   - `test_chunked_file_cat_works` - Cat command on chunked files
   - `test_chunked_deduplication` - Chunk sharing between files
   - `test_chunking_boundary_cases` - Exactly 1MB, just under 1MB

3. **Integration Tests:**
   - `test_compression_on_tree_with_mixed_sizes` - Directory with various file sizes
   - `test_gc_works_with_chunked_objects` - GC handles chunks correctly
   - `test_object_format_version` - New objects use v2
   - `test_stat_shows_compression_info` - Stat command output

**Existing test suites (still passing):**
- `test_add.py` - 50+ tests for adding files/directories
- `test_materialize.py` - 20+ tests for restoration
- `test_gc.py` - GC and orphan detection
- `test_deduplication.py` - Content deduplication
- `test_integration.py` - End-to-end workflows
- And more...

## Key Test Scenarios

### 1. Compression Verification

```bash
# Run compression-specific tests
cargo test -p casq_core test_compression

# Python integration tests
cd casq-test
uv run pytest tests/test_compression_chunking.py::test_medium_file_is_compressed -v
uv run pytest tests/test_compression_chunking.py::test_compression_reduces_storage -v
```

**What's tested:**
- 4KB threshold (files below not compressed)
- zstd compression actually reduces size
- Round-trip integrity (compress → decompress)
- Hash stability (hash computed on uncompressed data)

### 2. Chunking Verification

```bash
# Run chunking-specific tests
cargo test -p casq_core chunking

# Python integration tests (slow - large files)
cd casq-test
uv run pytest tests/test_compression_chunking.py -k chunked -v
```

**What's tested:**
- 1MB threshold (files below not chunked)
- Multiple chunks created for large files
- Chunk boundaries (min 256KB, avg 512KB, max 1MB)
- Deterministic chunking (same file → same chunks)
- Chunk deduplication (shared content → shared chunks)

### 3. Backward Compatibility

```bash
# All existing tests should still pass
cargo test
cd casq-test && uv run pytest
```

**What's tested:**
- v1 objects can still be read
- Mixed v1/v2 stores work correctly
- No API breaking changes
- All existing commands work

### 4. End-to-End Workflows

```bash
cd casq-test
uv run pytest tests/test_integration.py -v
```

**What's tested:**
- Add → materialize → verify
- Add → GC → materialize (referenced objects preserved)
- Multiple file sizes in same directory
- Refs work with compressed/chunked objects

## Manual Verification (Without Network)

If the Python test environment cannot be set up due to network restrictions, you can manually verify functionality:

```bash
# Build
cargo build --release

# Initialize store
./target/release/casq init /tmp/test-store

# Test 1: Small file (no compression)
echo "small" > /tmp/small.txt
HASH1=$(./target/release/casq add /tmp/small.txt --root /tmp/test-store | awk '{print $1}')
echo "Small file hash: $HASH1"

# Test 2: Medium file (compression)
dd if=/dev/urandom of=/tmp/medium.bin bs=1K count=10 2>/dev/null
HASH2=$(./target/release/casq add /tmp/medium.bin --root /tmp/test-store | awk '{print $1}')
echo "Medium file hash: $HASH2"

# Test 3: Large file (chunking)
dd if=/dev/urandom of=/tmp/large.bin bs=1M count=2 2>/dev/null
HASH3=$(./target/release/casq add /tmp/large.bin --root /tmp/test-store | awk '{print $1}')
echo "Large file hash: $HASH3"

# Verify materialization
./target/release/casq materialize $HASH3 /tmp/restored.bin --root /tmp/test-store
diff /tmp/large.bin /tmp/restored.bin && echo "✓ Large file integrity verified"

# Check object counts
echo "Total objects created:"
find /tmp/test-store/objects -type f | wc -l
```

## Debugging Tests

### Run with verbose output
```bash
cargo test -- --nocapture --test-threads=1
```

### Run specific test
```bash
cargo test -p casq_core test_chunk_file_basic -- --nocapture
```

### Check test list
```bash
cargo test -- --list
```

## Continuous Integration

Recommended CI pipeline:

```yaml
test:
  script:
    - cargo fmt -- --check
    - cargo clippy -- -D warnings
    - cargo test --all
    - cargo build
    - cd casq-test && uv run pytest -v
```

## Performance Benchmarks (Optional)

For performance testing, use criterion (not yet implemented):

```bash
# If benchmarks are added in the future
cargo bench
```

## Success Criteria

**All tests passing:**
- ✅ 92 Rust unit tests pass
- ✅ 25+ Python integration tests pass (when network available)
- ✅ No clippy warnings
- ✅ Code formatted with rustfmt
- ✅ Manual verification succeeds

## Troubleshooting

### Python tests fail: "casq binary not found"
```bash
# Ensure debug binary is built
cargo build
ls -l target/debug/casq
```

### Tests timeout or hang
```bash
# Run with fewer threads
cargo test -- --test-threads=1
```

### Large file tests fail (disk space)
```bash
# Check available space
df -h /tmp
# Python tests marked with @pytest.mark.slow can be skipped
cd casq-test && uv run pytest -m "not slow"
```

## Test File Locations

- **Rust unit tests:** Inline in `casq_core/src/*.rs` files
- **Python integration tests:** `casq-test/tests/*.py`
- **Test helpers:** `casq-test/helpers/*.py`
- **Test fixtures:** `casq-test/fixtures/*.py`
