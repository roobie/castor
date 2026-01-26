"""
Helper utilities for casq tests.
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent


def assert_json_success(stdout: str, expected_keys: list = None) -> Dict[str, Any]:
    """
    Parse JSON output and assert success field is True.

    Args:
        stdout: JSON string from command output
        expected_keys: Optional list of keys to assert presence

    Returns:
        Parsed JSON dict
    """
    data = json.loads(stdout)
    assert data.get("success") is True, f"Expected success=True, got: {data}"
    assert data.get("result_code") == 0, (
        f"Expected result_code=0, got: {data.get('result_code')}"
    )

    if expected_keys:
        for key in expected_keys:
            assert key in data, f"Expected key '{key}' in JSON output"

    return data


def assert_json_error(stderr: str) -> Dict[str, Any]:
    """
    Parse JSON error output and assert success field is False.

    Args:
        stderr: JSON string from command error output

    Returns:
        Parsed JSON dict
    """
    data = json.loads(stderr)
    assert data.get("success") is False, f"Expected success=False, got: {data}"
    assert data.get("result_code") != 0, (
        f"Expected non-zero result_code, got: {data.get('result_code')}"
    )
    assert "error" in data, "Expected 'error' field in error output"

    return data


def write_test_file(path: Path, content: str = "test content\n"):
    """Create a test file with given content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def write_test_tree(root: Path):
    """Create a test directory tree for testing."""
    (root / "file1.txt").write_text("file 1 content\n")
    (root / "file2.txt").write_text("file 2 content\n")
    (root / "subdir").mkdir()
    (root / "subdir" / "nested.txt").write_text("nested content\n")


def compare_golden(actual: str, golden_name: str, update: bool = False) -> bool:
    """
    Compare actual output against golden file.

    Args:
        actual: Actual output string
        golden_name: Name of golden file (e.g., "help.txt")
        update: If True, update golden file with actual content

    Returns:
        True if matches (or was updated), raises AssertionError otherwise
    """
    golden_path = Path(__file__).parent / "golden" / golden_name

    if update or not golden_path.exists():
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(actual)
        if not update:
            print(f"Created golden file: {golden_path}")
        return True

    expected = golden_path.read_text()
    assert actual == expected, f"Output doesn't match golden file: {golden_path}"
    return True


def run_casq(
    casq_bin, env, *args, input=None, check=False
) -> subprocess.CompletedProcess:
    """
    Helper to run casq and capture stdout/stderr.

    Args:
        casq_bin: Path to casq binary
        env: Environment dict (should include CASQ_ROOT)
        *args: Command arguments
        input: Optional stdin input (str)
        check: If True, raise CalledProcessError on non-zero exit

    Returns:
        CompletedProcess with stdout/stderr captured
    """
    return subprocess.run(
        [str(casq_bin), *args],
        input=input,
        env=env,
        cwd=ROOT,  # Run from workspace root
        text=True,
        capture_output=True,
        check=check,
    )
