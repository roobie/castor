"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path
from helpers.cli import CastorCLI
from fixtures import sample_files


@pytest.fixture(scope="session")
def casq_binary() -> Path:
    """
    Path to the compiled Castor binary.

    Returns:
        Path to casq binary

    Raises:
        FileNotFoundError if binary doesn't exist
    """
    # Look for binary in workspace/target/debug
    binary_path = Path(__file__).parent.parent / "target" / "debug" / "casq"

    if not binary_path.exists():
        raise FileNotFoundError(
            f"Castor binary not found at {binary_path}. "
            "Run 'cargo build -p casq' first."
        )

    return binary_path


@pytest.fixture
def workspace(tmp_path) -> Path:
    """
    Temporary workspace directory for creating test files.

    Args:
        tmp_path: Pytest's temporary directory fixture

    Returns:
        Path to workspace directory
    """
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()
    return workspace_dir


@pytest.fixture
def casq_store(tmp_path) -> Path:
    """
    Path for a Castor store (not initialized).

    Args:
        tmp_path: Pytest's temporary directory fixture

    Returns:
        Path to store directory
    """
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    return store_dir


@pytest.fixture
def initialized_store(casq_store, cli) -> Path:
    """
    Pre-initialized Castor store.

    Args:
        casq_store: Store directory fixture
        cli: CLI wrapper fixture

    Returns:
        Path to initialized store
    """
    cli.init(root=casq_store)
    return casq_store


@pytest.fixture
def cli(casq_binary) -> CastorCLI:
    """
    Configured CLI wrapper instance.

    Args:
        casq_binary: Binary path fixture

    Returns:
        CastorCLI instance
    """
    return CastorCLI(casq_binary)


@pytest.fixture
def sample_file(workspace) -> Path:
    """
    Create a simple sample file for testing.

    Args:
        workspace: Workspace directory fixture

    Returns:
        Path to sample file
    """
    return sample_files.create_sample_file(
        workspace / "sample.txt",
        "Hello, Castor!\n"
    )


@pytest.fixture
def sample_binary(workspace) -> Path:
    """
    Create a small binary file for testing.

    Args:
        workspace: Workspace directory fixture

    Returns:
        Path to binary file
    """
    return sample_files.create_binary_file(
        workspace / "binary.dat",
        size=1024,
        pattern=b"\xDE\xAD\xBE\xEF"
    )


@pytest.fixture
def sample_tree(workspace) -> Path:
    """
    Create a sample directory tree.

    Args:
        workspace: Workspace directory fixture

    Returns:
        Path to tree root
    """
    return sample_files.create_directory_tree(
        workspace / "tree",
        sample_files.SIMPLE_TREE
    )


@pytest.fixture
def nested_tree(workspace) -> Path:
    """
    Create a nested directory tree.

    Args:
        workspace: Workspace directory fixture

    Returns:
        Path to tree root
    """
    return sample_files.create_directory_tree(
        workspace / "nested",
        sample_files.NESTED_TREE
    )


@pytest.fixture
def complex_tree(workspace) -> Path:
    """
    Create a complex directory tree.

    Args:
        workspace: Workspace directory fixture

    Returns:
        Path to tree root
    """
    return sample_files.create_directory_tree(
        workspace / "complex",
        sample_files.COMPLEX_TREE
    )


# Test organization markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "smoke: marks tests as smoke tests (quick validation)"
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow running"
    )
    config.addinivalue_line(
        "markers",
        "edge_case: marks tests as edge case scenarios"
    )
