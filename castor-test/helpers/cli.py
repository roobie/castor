"""CLI invocation wrapper for Castor."""

import subprocess
from pathlib import Path
from typing import Optional, Union


class CastorCLI:
    """Wrapper for invoking the Castor CLI binary."""

    def __init__(self, binary_path: Path, default_root: Optional[Path] = None):
        """
        Initialize CLI wrapper.

        Args:
            binary_path: Path to the castor binary
            default_root: Default store root to use if not overridden
        """
        self.binary_path = binary_path
        self.default_root = default_root

    def run(
        self,
        *args: Union[str, Path],
        env: Optional[dict] = None,
        expect_success: bool = True,
        input_data: Optional[str] = None,
        root: Optional[Path] = None,
        binary_mode: bool = False,
    ) -> subprocess.CompletedProcess:
        """
        Run castor with the given arguments.

        Args:
            *args: Command-line arguments
            env: Environment variables to set (merged with current env)
            expect_success: If True, check=True for subprocess.run
            input_data: Data to send to stdin
            root: Store root to use (overrides default_root)
            binary_mode: If True, return binary stdout/stderr instead of text

        Returns:
            CompletedProcess instance
        """
        cmd = [str(self.binary_path)]

        # Add --root if specified
        effective_root = root if root is not None else self.default_root
        if effective_root is not None:
            cmd.extend(["--root", str(effective_root)])

        # Add remaining arguments
        cmd.extend(str(arg) for arg in args)

        # Prepare environment
        import os
        final_env = os.environ.copy()
        if env:
            final_env.update(env)

        # Run command
        return subprocess.run(
            cmd,
            capture_output=True,
            text=(not binary_mode),
            input=input_data,
            check=expect_success,
            env=final_env,
        )

    def init(
        self,
        root: Optional[Path] = None,
        algo: str = "blake3",
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """Initialize a new store."""
        args = ["init"]
        if algo != "blake3":
            args.extend(["--algo", algo])
        return self.run(*args, root=root, expect_success=expect_success)

    def add(
        self,
        *paths: Path,
        root: Optional[Path] = None,
        ref_name: Optional[str] = None,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """Add files or directories to the store."""
        args = ["add"]
        if ref_name:
            args.extend(["--ref-name", ref_name])
        args.extend(str(p) for p in paths)
        return self.run(*args, root=root, expect_success=expect_success)

    def materialize(
        self,
        hash_str: str,
        dest: Path,
        root: Optional[Path] = None,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """Materialize an object to a destination path."""
        return self.run(
            "materialize", hash_str, str(dest), root=root, expect_success=expect_success
        )

    def cat(
        self,
        hash_str: str,
        root: Optional[Path] = None,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """Output a blob to stdout."""
        return self.run("cat", hash_str, root=root, expect_success=expect_success, binary_mode=True)

    def ls(
        self,
        hash_or_empty: Optional[str] = None,
        root: Optional[Path] = None,
        long_format: bool = False,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """List refs or tree contents."""
        args = ["ls"]
        if long_format:
            args.append("-l")
        if hash_or_empty:
            args.append(hash_or_empty)
        return self.run(*args, root=root, expect_success=expect_success)

    def stat(
        self,
        hash_str: str,
        root: Optional[Path] = None,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """Show object metadata."""
        return self.run("stat", hash_str, root=root, expect_success=expect_success)

    def gc(
        self,
        root: Optional[Path] = None,
        dry_run: bool = False,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run garbage collection."""
        args = ["gc"]
        if dry_run:
            args.append("--dry-run")
        return self.run(*args, root=root, expect_success=expect_success)

    def refs_add(
        self,
        name: str,
        hash_str: str,
        root: Optional[Path] = None,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """Add a named reference."""
        return self.run(
            "refs", "add", name, hash_str, root=root, expect_success=expect_success
        )

    def refs_list(
        self,
        root: Optional[Path] = None,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """List all references."""
        return self.run("refs", "list", root=root, expect_success=expect_success)

    def refs_rm(
        self,
        name: str,
        root: Optional[Path] = None,
        expect_success: bool = True,
    ) -> subprocess.CompletedProcess:
        """Remove a named reference."""
        return self.run("refs", "rm", name, root=root, expect_success=expect_success)
