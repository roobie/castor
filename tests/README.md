# casq Integration Tests

Black-box integration tests for the `casq` CLI using pytest.

## Overview

These tests execute the real `casq` binary as a subprocess, verifying:
- CLI UX and help text
- Core workflow (put, list, get, materialize)
- Metadata inspection
- Garbage collection and orphan detection
- Reference management
- Error handling and edge cases
- JSON output format

Each test runs in an isolated temporary store using `CASQ_ROOT` environment variable.

## Test Structure

```
tests/
├── conftest.py           # Pytest fixtures and shared utilities
├── helpers.py            # Helper functions for assertions
├── requirements.txt      # Python dependencies
├── test_help.py         # Help text and CLI UX tests
├── test_initialize.py   # Store initialization tests
├── test_put_list_get.py # Core workflow tests
├── test_metadata.py     # Metadata inspection tests
├── test_gc_orphans.py   # GC and orphan detection tests
├── test_references.py   # Reference management tests
├── test_errors.py       # Error handling tests
└── golden/              # Golden files for UX stability testing
```

## Writing New Tests

Use the `casq_env` fixture for isolated test environments:

```python
from conftest import run_casq

def test_my_feature(casq_env):
    casq_bin, env, root = casq_env

    # Initialize store
    run_casq(casq_bin, env, "initialize")

    # Run your test
    proc = run_casq(casq_bin, env, "put", "-", input="test\n")
    assert proc.returncode == 0
```

Use helper functions for common assertions:

```python
from helpers import assert_json_success, write_test_file

def test_json_output(casq_env):
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc = run_casq(casq_bin, env, "--json", "references", "list")
    data = assert_json_success(proc.stdout, ["refs"])
    assert isinstance(data["refs"], list)
```

## Notes

- Tests use `tmp_path` fixture for isolation (cleaned up automatically)
- Binary is built once per session and reused
- Each test gets fresh store in `tmp_path/casq-store`
- Tests are independent and can run in parallel
- Golden files capture expected UX output (update intentionally)

## Coverage

Coverage reporting for the `casq_core` crate is available via the mise task added to the repository. It uses `cargo-tarpaulin` to produce HTML and XML (Cobertura) reports.

```bash
# Generate coverage reports for casq_core
mise run coverage_core
# Reports will be written to target/coverage/casq_core/
```

CI pipelines may ingest the XML output for dashboards or quality gates.
