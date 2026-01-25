"""Tests for 'casq put' command."""

import pytest
import os
import stat
from helpers.verification import (
    verify_object_exists,
)


@pytest.mark.smoke
def test_put_single_regular_file(cli, initialized_store, sample_file):
    """Test putting a single regular file."""
    result = cli.put(sample_file, root=initialized_store)

    assert result.returncode == 0
    # Output should contain a hash
    hash_output = result.stdout.strip()
    assert len(hash_output) == 64  # BLAKE3 hex length
    verify_object_exists(initialized_store, hash_output)


def test_put_file_returns_correct_hash_format(cli, initialized_store, sample_file):
    """Test that put returns valid hex hash."""
    result = cli.put(sample_file, root=initialized_store)

    hash_output = result.stdout.strip()
    # Should be valid hex
    int(hash_output, 16)
    assert len(hash_output) == 64
