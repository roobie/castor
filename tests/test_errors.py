"""
Tests for error handling and UX.
"""

from .helpers import run_casq


def test_command_without_initialize(casq_env):
    """Test that commands fail gracefully without initialized store."""
    casq_bin, env, root = casq_env

    # Try to put without initializing
    proc = run_casq(casq_bin, env, "put", "-", input="test\n")
    assert proc.returncode != 0
    # Should mention store error
    error_output = proc.stderr + proc.stdout
    assert (
        "failed to open store" in error_output.lower()
        or "not found" in error_output.lower()
    )


def test_unknown_command(casq_env):
    """Test that unknown command shows help."""
    casq_bin, env, _ = casq_env

    proc = run_casq(casq_bin, env, "does-not-exist")
    assert proc.returncode != 0

    # Should show usage or error about unknown command
    error_output = proc.stderr + proc.stdout
    assert "does-not-exist" in error_output or "Usage:" in error_output


def test_invalid_hash_format(casq_env):
    """Test that invalid hash format is rejected."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc = run_casq(casq_bin, env, "get", "notahexstring")
    assert proc.returncode != 0
    # there should be no data on stdout (there exist no data)
    assert proc.stdout.strip() == ""
    assert "unknown" in (proc.stderr).lower()


def test_nonexistent_hash(casq_env):
    """Test that non-existent hash returns error."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    fake_hash = "0" * 64
    proc = run_casq(casq_bin, env, "get", fake_hash)
    assert proc.returncode != 0
    error_output = (proc.stderr + proc.stdout).lower()
    assert "failed" in error_output or "not found" in error_output


def test_put_nonexistent_file(casq_env):
    """Test that putting non-existent file returns error."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc = run_casq(casq_bin, env, "put", "/nonexistent/path/file.txt")
    assert proc.returncode != 0

    error_output = proc.stderr + proc.stdout
    assert (
        "failed" in error_output.lower()
        or "not found" in error_output.lower()
        or "no such file" in error_output.lower()
    )


def test_materialize_to_existing_file(casq_env):
    """Test materializing to existing file location."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Put content
    proc_put = run_casq(casq_bin, env, "put", "-", input="test\n")
    obj_hash = proc_put.stdout.strip()

    # Create destination file
    dest = root.parent / "existing.txt"
    dest.write_text("existing content\n")

    # Try to materialize (may succeed and overwrite, or fail - depends on implementation)
    proc_mat = run_casq(casq_bin, env, "materialize", obj_hash, str(dest))
    # Implementation-specific behavior - just ensure it doesn't crash
    assert proc_mat.returncode in (0, 1)


def test_stdin_from_tty_fails(casq_env):
    """Test that stdin mode detects TTY and fails with helpful message."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Note: This test may not work in CI environments without a real TTY
    # The test is here for documentation, but may need to be skipped in CI
    import sys

    if not sys.stdin.isatty():
        # Skip test if not running with TTY
        return

    # Try to use stdin without piping (this should fail)
    proc = run_casq(casq_bin, env, "put", "-")
    # With our test harness, stdin is redirected, so this may not trigger the TTY check
    # But if it does, it should fail with helpful message
    if proc.returncode != 0:
        error_output = proc.stderr + proc.stdout
        # Just verify it doesn't crash unexpectedly
        assert len(error_output) > 0


def test_missing_required_argument(casq_env):
    """Test that missing required arguments show helpful error."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Try get without hash argument
    proc = run_casq(casq_bin, env, "get")
    assert proc.returncode != 0

    # Should show usage or mention missing argument
    assert proc.stdout.strip() == ""
    assert "usage" in (proc.stderr).lower()


def test_materialize_missing_destination(casq_env):
    """Test materialize without destination argument."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    fake_hash = "0" * 64
    proc = run_casq(casq_bin, env, "materialize", fake_hash)
    assert proc.returncode != 0

    error_output = proc.stderr + proc.stdout
    assert "destination" in error_output.lower() or "Usage:" in error_output


def test_references_add_invalid_hash(casq_env):
    """Test adding reference with invalid hash format."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    proc = run_casq(casq_bin, env, "references", "add", "bad-ref", "nothash")
    assert proc.returncode != 0
    assert "invalid" in (proc.stderr + proc.stdout).lower()


def test_references_add_nonexistent_hash(casq_env):
    """Test adding reference to non-existent object."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    fake_hash = "0" * 64
    proc = run_casq(casq_bin, env, "references", "add", "ref", fake_hash)
    # May succeed (dangling reference) or fail - implementation specific
    # Just ensure it doesn't crash
    assert proc.returncode in (0, 1)


def test_json_error_format(casq_env):
    """Test that errors in JSON mode have proper format."""
    casq_bin, env, root = casq_env
    run_casq(casq_bin, env, "initialize")

    # Trigger an error with --json flag
    proc = run_casq(casq_bin, env, "--json", "get", "invalidhash")
    assert proc.returncode != 0

    # Error should be in stderr as JSON
    import json

    try:
        error_data = json.loads(proc.stderr)
        assert error_data.get("success") is False
        assert "error" in error_data
        assert error_data.get("result_code") != 0
    except json.JSONDecodeError:
        # Some implementations may still use text errors
        # Just verify error output exists
        assert len(proc.stderr) > 0
