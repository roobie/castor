"""Tests for 'casq orphans' command."""

import pytest
import os
import sys
import stat
from pathlib import Path
from fixtures import sample_files
from helpers.verification import (
    verify_object_exists,
    get_object_type,
    parse_tree_entries,
    count_objects,
    list_all_refs,
)


@pytest.mark.smoke
def test_add_single_regular_file_and_it_should_be_an_orphan(
    cli, initialized_store, sample_file
):
    """Test adding a single regular file."""
    result_add = cli.add(sample_file, root=initialized_store)

    assert result_add.returncode == 0
    # Output should contain a hash
    hash_output = result_add.stdout.strip().split()[0]
    assert len(hash_output) == 64  # BLAKE3 hex length
    verify_object_exists(initialized_store, hash_output)

    result = cli.orphans(root=initialized_store)
    assert result.returncode == 0
    assert result.stdout.strip() == hash_output
