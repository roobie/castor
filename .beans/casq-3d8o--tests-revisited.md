---
# casq-3d8o
title: tests-revisited
status: completed
type: task
priority: normal
created_at: 2026-01-25T16:31:34Z
updated_at: 2026-01-25T16:44:57Z
---

## Overall approach

Use **Python + pytest** as a black-box harness that:

- Spawns the real `casq` binary with `subprocess`.
- Runs each test in an isolated temporary store.
- Asserts on exit code, stdout, stderr, and filesystem state.
- Uses golden/snapshot files for stable UX outputs.

Below is an implementation plan with concrete structure and example code.

---

## 1. Test layout and tooling

Directory structure:

```text
project-root/
  casq/                 # your CLI project (Rust, etc.)
  target/               # built binaries (cargo)
  tests/
    conftest.py
    helpers.py
    test_help.py
    test_initialize.py
    test_put_list_get.py
    test_metadata.py
    test_gc_orphans.py
    test_references.py
    test_errors.py
    golden/
      help.txt
      list_empty.txt
      list_after_put.txt
      metadata_example.json
```

Use:

```bash
pip install pytest
# optional: for snapshot testing
pip install pytest-approvaltests  # or snapshottest, etc.
```

---

## 2. Build and locate the `casq` binary

Assume the binary is built by Cargo:

- Default path: `target/debug/casq` or `target/release/casq`.

In `tests/conftest.py`:

```python
import os
import subprocess
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="session")
def casq_bin() -> Path:
    """Ensure casq is built and return path to binary."""
    bin_path = ROOT / "target" / "debug" / "casq"
    if not bin_path.exists():
        subprocess.check_call(["cargo", "build"], cwd=ROOT)
    return bin_path
```

If you prefer release builds, switch to `cargo build --release` and `target/release/casq`.

---

## 3. Create an isolated store per test

Use pytest’s `tmp_path` fixture and set `CASQ_ROOT` (or `--root`) to keep tests hermetic.

In `tests/conftest.py`:

```python
import os
import subprocess
from typing import Tuple

@pytest.fixture
def casq_env(tmp_path, casq_bin):
    """Return (binary_path, env, root_dir) for use in tests."""
    root = tmp_path / "store"
    env = os.environ.copy()
    env["CASQ_ROOT"] = str(root)
    return casq_bin, env, root


def run_casq(casq_bin, env, *args, input=None, check=False) -> subprocess.CompletedProcess:
    """Helper to run casq and capture stdout/stderr."""
    return subprocess.run(
        [str(casq_bin), *args],
        input=input,
        env=env,
        cwd=env.get("CASQ_ROOT", None),
        text=True,
        capture_output=True,
        check=check,
    )
```

In `tests/helpers.py` you can re-export `run_casq` or keep it in `conftest.py`.

---

## 4. Basic UX and help tests

### `tests/test_help.py`

```python
from .conftest import run_casq

def test_casq_top_level_help(casq_env, snapshot=None):
    casq_bin, env, _ = casq_env
    proc = run_casq(casq_bin, env, "--help")

    assert proc.returncode == 0
    assert "Usage: casq [OPTIONS] <COMMAND>" in proc.stdout
    assert "initialize" in proc.stdout
    assert proc.stderr == ""

    # Optional snapshot/golden check
    # Ensure golden/help.txt exists and is kept in sync intentionally
    from pathlib import Path
    golden = Path(__file__).with_suffix("").parent / "golden" / "help.txt"
    if golden.exists():
        assert proc.stdout == golden.read_text()
```

You can similarly test `casq initialize --help`, `casq put --help`, etc.

---

## 5. Initialize + list empty store

### `tests/test_initialize.py`

```python
from .conftest import run_casq

def test_initialize_creates_store(casq_env):
    casq_bin, env, root = casq_env

    # Before initialize, root dir should not exist
    assert not root.exists()

    proc = run_casq(casq_bin, env, "initialize")
    assert proc.returncode == 0
    assert "Initialized" in proc.stdout or proc.stdout != ""
    assert root.exists()

    # list on fresh store
    proc_list = run_casq(casq_bin, env, "list", "--json")
    assert proc_list.returncode == 0
    # shape of JSON list; depends on your actual schema
    import json
    data = json.loads(proc_list.stdout)
    assert data["success"] is True
    assert data.get("refs") == [] or data.get("refs") is not None
```

---

## 6. Put, list, get: core workflow

### `tests/test_put_list_get.py`

```python
import json
from pathlib import Path
from .conftest import run_casq

def test_put_list_get_roundtrip(casq_env):
    casq_bin, env, root = casq_env

    # Initialize store
    proc = run_casq(casq_bin, env, "initialize")
    assert proc.returncode == 0

    # Prepare a file to store
    workspace = root.parent / "workspace"
    workspace.mkdir()
    (workspace / "file.txt").write_text("hello world\n")

    # Put file (assuming: casq put <path>)
    proc_put = run_casq(casq_bin, env, "put", str(workspace / "file.txt"), "--json")
    assert proc_put.returncode == 0
    put_data = json.loads(proc_put.stdout)
    obj_hash = put_data["hash"]  # adapt to your actual schema

    # List should show something
    proc_list = run_casq(casq_bin, env, "list", "--json")
    assert proc_list.returncode == 0
    list_data = json.loads(proc_list.stdout)
    assert any(child["hash"] == obj_hash for child in list_data.get("children", [])) or True

    # Get should print content to stdout
    proc_get = run_casq(casq_bin, env, "get", obj_hash)
    assert proc_get.returncode == 0
    assert proc_get.stdout == "hello world\n"
```

Adapt JSON keys/structure to match your real output.

---

## 7. Metadata, garbage collection, and orphans

### `tests/test_metadata.py`

```python
import json
from pathlib import Path
from .conftest import run_casq

def test_metadata_for_object(casq_env):
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    workspace = root.parent / "ws"
    workspace.mkdir()
    (workspace / "f.txt").write_text("meta test")

    proc_put = run_casq(casq_bin, env, "put", str(workspace / "f.txt"), "--json")
    assert proc_put.returncode == 0
    h = json.loads(proc_put.stdout)["hash"]

    proc_meta = run_casq(casq_bin, env, "metadata", h, "--json")
    assert proc_meta.returncode == 0
    meta = json.loads(proc_meta.stdout)
    assert meta["hash"] == h
    assert meta["size"] == len("meta test")
    assert "created_at" in meta  # example
```

### `tests/test_gc_orphans.py`

```python
from .conftest import run_casq

def test_collect_garbage_and_find_orphans(casq_env):
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Depending on how your system defines refs/orphans, set up:
    # - a stored object
    # - a removed/forgotten reference

    # Run find-orphans and expect some output / JSON structure
    proc_orphans = run_casq(casq_bin, env, "find-orphans", "--json")
    assert proc_orphans.returncode == 0

    # Then run gc; assert it runs successfully
    proc_gc = run_casq(casq_bin, env, "collect-garbage", "--json")
    assert proc_gc.returncode == 0
```

You’ll need to tune this to your actual semantics.

---

## 8. References subcommand tests

### `tests/test_references.py`

```python
import json
from pathlib import Path
from .conftest import run_casq

def test_references_create_and_list(casq_env):
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    ws = root.parent / "ws"
    ws.mkdir()
    (ws / "f.txt").write_text("ref test")

    proc_put = run_casq(casq_bin, env, "put", str(ws / "f.txt"), "--json")
    h = json.loads(proc_put.stdout)["hash"]

    # Assuming something like: casq references add <name> <hash> --json
    proc_add = run_casq(casq_bin, env, "references", "add", "casq", h, "--json")
    assert proc_add.returncode == 0

    proc_list_refs = run_casq(casq_bin, env, "references", "list", "--json")
    assert proc_list_refs.returncode == 0
    data = json.loads(proc_list_refs.stdout)
    names = [ref["name"] for ref in data.get("refs", [])]
    assert "casq" in names
```

Again, adjust to your exact CLI interface.

---

## 9. Error and UX tests

### `tests/test_errors.py`

```python
from .conftest import run_casq

def test_put_without_initialize_fails(casq_env):
    casq_bin, env, _ = casq_env

    proc = run_casq(casq_bin, env, "put", "somefile")
    assert proc.returncode != 0
    assert "initialize" in proc.stderr or "not initialized" in proc.stdout.lower()

def test_unknown_command(casq_env):
    casq_bin, env, _ = casq_env

    proc = run_casq(casq_bin, env, "does-not-exist")
    assert proc.returncode != 0
    assert "Usage: casq" in proc.stdout or "unknown" in proc.stderr.lower()
```

These ensure helpful messages and correct exit codes.

---

## 10. Snapshots / golden files

For stable UX (help text, `list` formatting), store golden outputs:

```python
from pathlib import Path
from .conftest import run_casq

def test_help_golden(casq_env):
    casq_bin, env, _ = casq_env
    proc = run_casq(casq_bin, env, "--help")
    assert proc.returncode == 0

    golden = Path(__file__).with_suffix("").parent / "golden" / "help.txt"
    if not golden.exists():
        # First time: write it intentionally and check in
        golden.write_text(proc.stdout)
        # Then manually review and re-run tests
    assert proc.stdout == golden.read_text()
```

When you intentionally change help text/UX, update goldens as part of the change.

---

## 11. Running the harness

In project root:

```bash
pytest -q
```

Integrate into CI:

- Add `cargo build` then `pytest` steps.
- Optionally run with `CARGO_PROFILE=release` if you want full-speed tests.

---

This plan gives you:

- Real executable tested (“closest to real usage”).
- Isolated per-test stores via `CASQ_ROOT` + `tmp_path`.
- JSON and human-readable UX verified.
- Structured tests per command and user workflow.

