"""Sample file and directory generators for tests."""

import stat
from pathlib import Path
from typing import Dict, Any, Union


def create_sample_file(path: Path, content: str) -> Path:
    """
    Create a simple text file.

    Args:
        path: File path to create
        content: Text content

    Returns:
        Path to created file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_binary_file(path: Path, size: int, pattern: bytes = b"\x00") -> Path:
    """
    Create a binary file of specific size.

    Args:
        path: File path to create
        size: Size in bytes
        pattern: Byte pattern to repeat (default: null bytes)

    Returns:
        Path to created file
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "wb") as f:
        if len(pattern) == 0:
            pattern = b"\x00"

        full_cycles = size // len(pattern)
        remainder = size % len(pattern)

        f.write(pattern * full_cycles)
        if remainder > 0:
            f.write(pattern[:remainder])

    return path


def create_executable_file(path: Path, content: str) -> Path:
    """
    Create an executable file with proper mode.

    Args:
        path: File path to create
        content: Script content

    Returns:
        Path to created file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)

    # Make executable (owner, group, others)
    current_mode = path.stat().st_mode
    path.chmod(current_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return path


def create_directory_tree(base: Path, structure: Dict[str, Any]) -> Path:
    """
    Create a nested directory tree from a dictionary specification.

    Args:
        base: Base directory path
        structure: Dict where keys are names and values are either:
            - str: file content
            - dict: subdirectory structure
            - None: empty directory

    Returns:
        Path to base directory

    Example:
        create_directory_tree(Path("/tmp/test"), {
            "file1.txt": "content",
            "subdir": {
                "file2.txt": "more content",
                "empty_dir": None,
            }
        })
    """
    base.mkdir(parents=True, exist_ok=True)

    for name, value in structure.items():
        path = base / name

        if value is None:
            # Empty directory
            path.mkdir(parents=True, exist_ok=True)

        elif isinstance(value, str):
            # File with content
            create_sample_file(path, value)

        elif isinstance(value, dict):
            # Subdirectory
            create_directory_tree(path, value)

        else:
            raise ValueError(f"Unsupported structure value type: {type(value)}")

    return base


def create_empty_file(path: Path) -> Path:
    """
    Create an empty file.

    Args:
        path: File path to create

    Returns:
        Path to created file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def create_file_with_mode(path: Path, content: str, mode: int) -> Path:
    """
    Create a file with specific permissions.

    Args:
        path: File path to create
        content: File content
        mode: Permission mode (e.g., 0o755)

    Returns:
        Path to created file
    """
    create_sample_file(path, content)
    path.chmod(mode)
    return path


def create_symlink(link_path: Path, target: Union[Path, str]) -> Path:
    """
    Create a symbolic link.

    Args:
        link_path: Path where the symlink should be created
        target: Target path (can be relative or absolute)

    Returns:
        Path to created symlink
    """
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(target)
    return link_path


# Common test file structures

SIMPLE_TREE = {
    "file1.txt": "Hello, world!",
    "file2.txt": "Another file",
}

NESTED_TREE = {
    "top.txt": "Top level",
    "dir1": {
        "file1.txt": "In dir1",
        "file2.txt": "Also in dir1",
    },
    "dir2": {
        "subdir": {
            "deep.txt": "Deep file",
        },
    },
}

COMPLEX_TREE = {
    "README.md": "# Project\n\nDocumentation here.",
    "src": {
        "main.py": "#!/usr/bin/env python3\nprint('hello')\n",
        "lib": {
            "utils.py": "def helper(): pass\n",
            "data.json": '{"key": "value"}',
        },
    },
    "tests": {
        "test_main.py": "def test_it(): assert True\n",
    },
    "empty_dir": None,
}

UNICODE_TREE = {
    "français.txt": "Bonjour!",
    "日本語.txt": "こんにちは",
    "emoji_📁": {
        "file_✨.txt": "sparkles",
    },
}
