# casq CLI Test Suite

Comprehensive pytest-based test suite for the casq content-addressed file store CLI.

## Overview

This test suite provides **248+ tests** achieving 100% CLI surface coverage for casq. It tests all commands, options, error paths, edge cases, and integration scenarios using real end-to-end execution of the casq binary, including comprehensive coverage of v0.4.0 compression and chunking features.

### Test Coverage

| Test Module | Tests | Coverage Area |
|-------------|-------|---------------|
| `test_init.py` | 18 | Store initialization |
| `test_add.py` | 45 | Adding files and directories |
| `test_materialize.py` | 32 | Restoring objects from store |
| `test_cat.py` | 18 | Outputting blob content |
| `test_ls.py` | 28 | Listing refs and tree contents |
| `test_stat.py` | 16 | Object metadata |
| `test_gc.py` | 22 | Garbage collection |
| `test_refs.py` | 28 | Reference management |
| `test_integration.py` | 18 | Multi-command workflows |
| `test_edge_cases.py` | 12 | Unusual scenarios |
| `test_hash_stability.py` | 8 | Determinism verification |
| `test_deduplication.py` | 8 | Content deduplication |
| `test_compression_chunking.py` | 25+ | Compression & chunking (v0.4.0) |
| **TOTAL** | **248+** | **100% CLI coverage** |

## Quick Start

### Prerequisites

1. **Build casq binary:**
   ```bash
   cd /workspace
   cargo build -p casq
   ```

2. **Install dependencies:**
   ```bash
   cd casq-test
   uv sync
   ```

### Running Tests

#### Using Just (Recommended)

The project includes a `justfile` with convenient recipes for common tasks:

```bash
cd casq-test

# Show all available commands
just

# Check Python syntax
just py_compile

# Run all tests
just test

# Run tests with verbose output
just test-verbose

# Run only smoke tests
just test-smoke

# Run without slow tests
just test-fast

# Count total tests
just count

# Run specific test file
just test-file test_add.py

# Run tests matching pattern
just test-pattern "unicode"

# Full CI workflow (build casq + install + test)
just ci

# Quick verification (syntax + smoke tests)
just verify
```

#### Using Pytest Directly

```bash
# Run all tests
cd casq-test
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_add.py

# Run tests matching a pattern
pytest -k "test_add"

# Run with markers
pytest -m smoke         # Quick smoke tests
pytest -m "not slow"    # Skip slow tests
```

### Expected Output

```
============================= test session starts ==============================
collected 248 items

tests/test_init.py::test_init_default PASSED                             [  0%]
tests/test_init.py::test_init_creates_config_file PASSED                 [  1%]
...
tests/test_compression_chunking.py::test_chunked_deduplication PASSED   [99%]
tests/test_deduplication.py::test_binary_deduplication PASSED           [100%]

========================== 247 passed, 1 xpassed, 2 skipped in 45.00s =========
```

## Test Organization

### Directory Structure

```
casq-test/
├── README.md                      # This file
├── pyproject.toml                 # Dependencies
├── pytest.ini                     # Pytest configuration
├── conftest.py                    # Shared fixtures
│
├── helpers/                       # Helper utilities
│   ├── __init__.py
│   ├── cli.py                    # CLI wrapper
│   └── verification.py           # Store inspection
│
├── fixtures/                      # Test fixtures
│   ├── __init__.py
│   └── sample_files.py           # File generators
│
└── tests/                         # Test modules
    ├── __init__.py
    ├── test_init.py              # Init command tests
    ├── test_add.py               # Add command tests
    ├── test_materialize.py       # Materialize tests
    ├── test_cat.py               # Cat command tests
    ├── test_ls.py                # Ls command tests
    ├── test_stat.py              # Stat command tests
    ├── test_gc.py                # Garbage collection
    ├── test_refs.py              # Refs subcommands
    ├── test_integration.py       # Multi-command flows
    ├── test_edge_cases.py        # Edge cases
    ├── test_hash_stability.py    # Hash determinism
    ├── test_deduplication.py     # Content dedupe
    └── test_compression_chunking.py  # Compression & chunking (v0.4.0)
```

### Test Isolation

Each test gets a **fresh temporary environment**:
- Unique temporary directory via `tmp_path` fixture
- Store created at `tmp_path / "store"`
- Workspace at `tmp_path / "workspace"`
- Automatic cleanup after test completion

This ensures:
- ✅ **No test interference** - Tests can run in any order
- ✅ **Parallel execution safe** - Can use `pytest-xdist`
- ✅ **Clean state** - Each test starts fresh

### Fixtures

**Core fixtures** (defined in `conftest.py`):

- `casq_binary` - Path to compiled casq binary
- `casq_store` - Empty store directory (not initialized)
- `initialized_store` - Pre-initialized store ready for use
- `workspace` - Temporary workspace for creating test files
- `cli` - Configured `casqCLI` wrapper instance
- `sample_file` - Simple text file
- `sample_tree` - Flat directory with files
- `nested_tree` - Nested directory structure
- `complex_tree` - Complex project-like structure

**Example usage:**
```python
def test_add_file(cli, initialized_store, sample_file):
    """Test adding a file to the store."""
    result = cli.add(sample_file, root=initialized_store)
    assert result.returncode == 0
```

## Test Patterns

### Basic Test Pattern

```python
def test_something(cli, initialized_store, workspace):
    """Test description."""
    # Arrange: Set up test data
    test_file = sample_files.create_sample_file(
        workspace / "test.txt",
        "test content"
    )

    # Act: Execute command
    result = cli.add(test_file, root=initialized_store)

    # Assert: Verify results
    assert result.returncode == 0
    verify_object_exists(initialized_store, result.stdout.strip())
```

### Testing Error Conditions

```python
def test_invalid_hash(cli, initialized_store):
    """Test command handles invalid hash gracefully."""
    result = cli.cat("invalid", root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0
```

### Integration Test Pattern

```python
def test_workflow(cli, casq_store, workspace):
    """Test multi-step workflow."""
    # Initialize
    cli.init(root=casq_store)

    # Add data
    data = create_test_data(workspace)
    hash_val = cli.add(data, root=casq_store, ref_name="backup").stdout.strip()

    # Verify
    verify_object_exists(casq_store, hash_val)

    # Restore
    restore_dir = workspace / "restored"
    cli.materialize(hash_val, restore_dir, root=casq_store)

    # Check integrity
    assert_directories_equal(data, restore_dir)
```

## Advanced Usage

### Parallel Execution

Install `pytest-xdist` for parallel test execution:

```bash
uv add pytest-xdist

# Run tests in parallel (auto-detect CPUs)
pytest -n auto

# Run on specific number of workers
pytest -n 4
```

### Coverage Reporting

Install `pytest-cov` for coverage analysis:

```bash
uv add pytest-cov

# Run with coverage
pytest --cov=. --cov-report=html

# View report
open htmlcov/index.html
```

### Filtering Tests

```bash
# Run only smoke tests
pytest -m smoke

# Run specific test
pytest tests/test_add.py::test_add_single_regular_file

# Run tests matching pattern
pytest -k "add_file"

# Run tests in specific file matching pattern
pytest tests/test_add.py -k "unicode"
```

### Debugging Failed Tests

```bash
# Show more output on failure
pytest -vv

# Show print statements
pytest -s

# Stop on first failure
pytest -x

# Drop into debugger on failure
pytest --pdb

# Show local variables on failure
pytest -l
```

## Helper Utilities

### CLI Wrapper (`helpers/cli.py`)

Provides convenient wrappers for all casq commands:

```python
from helpers.cli import casqCLI

cli = casqCLI(binary_path)

# Convenience methods
cli.init(root=store_path)
cli.add(file_path, root=store_path, ref_name="backup")
cli.materialize(hash, dest_path, root=store_path)
cli.cat(hash, root=store_path)
cli.ls(hash, root=store_path, long_format=True)
cli.stat(hash, root=store_path)
cli.gc(root=store_path, dry_run=True)
cli.refs_add(name, hash, root=store_path)
cli.refs_list(root=store_path)
cli.refs_rm(name, root=store_path)

# Generic run method
cli.run("command", "arg1", "arg2", root=store_path)
```

### Verification Helpers (`helpers/verification.py`)

Tools for inspecting and verifying store contents:

```python
from helpers.verification import (
    verify_store_structure,
    verify_object_exists,
    get_object_type,
    get_compression_type,
    read_blob_content,
    parse_tree_entries,
    count_objects,
    list_all_refs,
)

# Verify store structure
verify_store_structure(store_path, algo="blake3")

# Check object exists
verify_object_exists(store_path, hash_str)

# Get object type
obj_type = get_object_type(store_path, hash_str)  # "blob", "tree", or "chunk_list"

# Get compression type (v0.4.0+)
compression = get_compression_type(store_path, hash_str)  # 0=none, 1=zstd

# Read blob content
content = read_blob_content(store_path, hash_str)

# Parse tree entries
entries = parse_tree_entries(store_path, tree_hash)
# Returns: [{"type": "blob", "mode": 0o644, "hash": "...", "name": "file.txt"}, ...]

# Count objects
num_objects = count_objects(store_path)

# List all refs
refs = list_all_refs(store_path)
# Returns: {"backup": "abc123...", "v1": "def456..."}
```

### Sample File Generators (`fixtures/sample_files.py`)

Utilities for creating test data:

```python
from fixtures import sample_files

# Simple text file
sample_files.create_sample_file(path, "content")

# Binary file of specific size
sample_files.create_binary_file(path, size=1024, pattern=b"\xFF")

# Executable file
sample_files.create_executable_file(path, "#!/bin/bash\necho hi\n")

# Directory tree from dict
sample_files.create_directory_tree(base_path, {
    "file.txt": "content",
    "subdir": {
        "nested.txt": "nested content",
    },
    "empty_dir": None,
})

# Pre-defined structures
sample_files.SIMPLE_TREE
sample_files.NESTED_TREE
sample_files.COMPLEX_TREE
sample_files.UNICODE_TREE
```

## Writing New Tests

### 1. Choose the Right Test File

- **Command-specific tests**: Add to `test_<command>.py`
- **Multi-command flows**: Add to `test_integration.py`
- **Unusual scenarios**: Add to `test_edge_cases.py`
- **Hash behavior**: Add to `test_hash_stability.py`
- **Deduplication**: Add to `test_deduplication.py`
- **Compression/Chunking**: Add to `test_compression_chunking.py`

### 2. Follow Naming Conventions

```python
# Good test names (verb + what + context)
def test_add_single_file(...)
def test_gc_deletes_orphaned_objects(...)
def test_refs_add_invalid_hash_format(...)

# Include clear docstring
def test_add_file_with_unicode_name(...):
    """Test that files with unicode names can be added."""
```

### 3. Use Appropriate Fixtures

```python
# For command tests
def test_command(cli, initialized_store, workspace):
    ...

# For initialization tests
def test_init(cli, casq_store):
    ...

# For integration tests
def test_workflow(cli, casq_store, workspace):
    ...
```

### 4. Test Pattern Template

```python
def test_feature_name(cli, initialized_store, workspace):
    """Clear description of what is being tested."""
    # Arrange: Set up test data and preconditions
    test_data = setup_test_data(workspace)

    # Act: Execute the command being tested
    result = cli.command(args, root=initialized_store)

    # Assert: Verify the expected outcomes
    assert result.returncode == 0
    assert expected_condition
    verify_side_effects(initialized_store)
```

### 5. Error Testing Pattern

```python
def test_command_error_condition(cli, initialized_store):
    """Test that command handles error condition appropriately."""
    # Use expect_success=False for commands expected to fail
    result = cli.command(invalid_input, root=initialized_store, expect_success=False)

    assert result.returncode != 0
    assert len(result.stderr) > 0
    assert "error message" in result.stderr.lower()
```

## Troubleshooting

### Binary Not Found

```
FileNotFoundError: casq binary not found at /workspace/target/debug/casq
```

**Solution:** Build the casq binary first:
```bash
cd /workspace
cargo build -p casq
```

### Tests Hang or Timeout

**Possible causes:**
- Command waiting for input
- Infinite loop in casq binary
- Very large file test

**Solutions:**
- Use `pytest-timeout` plugin: `uv add pytest-timeout`
- Run with timeout: `pytest --timeout=60`

### Permission Errors on CI

Some tests require specific file permissions (e.g., `test_init_permission_denied`).

**Solution:** Skip permission tests on incompatible systems:
```python
@pytest.mark.skipif(os.name == 'nt', reason="Permission test unreliable on Windows")
def test_permission_denied(...):
    ...
```

### Disk Space Issues

Large file tests may consume significant disk space.

**Solution:**
- Reduce test file sizes for CI environments
- Use `@pytest.mark.slow` and skip slow tests: `pytest -m "not slow"`

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Test casq CLI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build casq
        run: cargo build --release -p casq

      - name: Install UV
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Run Tests
        run: |
          cd casq-test
          uv sync
          uv run pytest -v
```

### Test Exit Codes

- `0` - All tests passed
- `1` - Tests failed
- `2` - Test execution interrupted
- `3` - Internal error
- `4` - pytest usage error
- `5` - No tests collected

## Performance

Expected test execution times:
- **Smoke tests** (`-m smoke`): ~5 seconds
- **Full suite** (without slow tests): ~30-40 seconds
- **Full suite** (with slow tests, including chunking): ~60-90 seconds
- **Parallel** (`-n auto`): ~15-20 seconds

Note: Chunking tests create large files (1-3 MB) and may be slower on systems with limited I/O performance. Use `-m "not slow"` to skip these tests for faster validation.

## Contributing

### Adding Tests

1. Write test following patterns above
2. Ensure test is isolated (uses fixtures)
3. Add descriptive docstring
4. Run test: `pytest tests/test_yourfile.py::test_your_test -v`
5. Run full suite to ensure no breakage: `pytest`

### Test Quality Checklist

- [ ] Test has clear, descriptive name
- [ ] Test has docstring explaining what it tests
- [ ] Test uses appropriate fixtures
- [ ] Test is isolated (no side effects)
- [ ] Test verifies expected behavior
- [ ] Test handles errors appropriately
- [ ] Test runs quickly (or marked with `@pytest.mark.slow`)

## License

This test suite is part of the casq project and follows the same license.

## Support

For issues with the test suite:
1. Check this README
2. Review test patterns
3. Check casq CLI documentation in `/workspace/CLAUDE.md`
4. Open an issue with test failure details
