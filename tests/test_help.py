"""
Tests for casq help text and UX output.
"""

from .helpers import run_casq


def test_top_level_help(casq_env):
    """Test that casq --help shows usage and commands."""
    casq_bin, env, _ = casq_env
    proc = run_casq(casq_bin, env, "--help")

    assert proc.returncode == 0
    assert "Content-addressed file store using BLAKE3" in proc.stdout
    assert "Commands:" in proc.stdout
    assert "initialize" in proc.stdout.lower()
    assert "put" in proc.stdout.lower()
    assert proc.stderr == ""


def test_version_flag(casq_env):
    """Test that casq --version shows version info."""
    casq_bin, env, _ = casq_env
    proc = run_casq(casq_bin, env, "--version")

    assert proc.returncode == 0
    assert "casq" in proc.stdout.lower()
    # Version output should be non-empty
    assert len(proc.stdout.strip()) > 0


def test_initialize_help(casq_env):
    """Test that casq initialize --help shows subcommand help."""
    casq_bin, env, _ = casq_env
    proc = run_casq(casq_bin, env, "initialize", "--help")

    assert proc.returncode == 0
    assert "Initialize a new store" in proc.stdout
    assert "algorithm" in proc.stdout.lower()


def test_put_help(casq_env):
    """Test that casq put --help shows subcommand help."""
    casq_bin, env, _ = casq_env
    proc = run_casq(casq_bin, env, "put", "--help")

    assert proc.returncode == 0
    assert "Put files or directories" in proc.stdout
    assert "reference" in proc.stdout.lower()


def test_references_help(casq_env):
    """Test that casq references --help shows reference subcommands."""
    casq_bin, env, _ = casq_env
    proc = run_casq(casq_bin, env, "references", "--help")

    assert proc.returncode == 0
    assert "Manage references" in proc.stdout
    assert "add" in proc.stdout.lower()
    assert "list" in proc.stdout.lower()
    assert "remove" in proc.stdout.lower()
