# castor

A content-addressed file store CLI using BLAKE3.

## Overview

**Castor** is a command-line tool for managing content-addressed storage. It stores files and directories by their cryptographic hash, providing automatic deduplication, garbage collection, and named references.

This is the CLI binary that uses the `castor_core` library.

## Installation

```bash
# Build from source
cargo build --release -p castor

# The binary will be at target/release/castor
# Install it by
cargo install --path ./castor
# Optionally, copy to your PATH
cp target/release/castor $HOME/.local/bin/
```

## Quick Start

```bash
# Initialize a new store
castor init

# Add files or directories
castor add myfile.txt
castor add mydir/

# Add with a named reference
castor add important-data/ --ref-name backup-2024

# List references
castor refs list

# List tree contents
castor ls <hash>

# Output blob content
castor cat <hash>

# Show object metadata
castor stat <hash>

# Materialize (restore) to filesystem
castor materialize <hash> ./restored

# Garbage collect unreferenced objects
castor gc --dry-run  # Preview
castor gc            # Actually delete
```

## Commands

### `castor init`

Initialize a new content-addressed store.

```bash
castor init [--algo blake3]

Options:
  --algo <ALGORITHM>  Hash algorithm (default: blake3)
```

Creates the store directory structure at the configured root (default: `./castor-store`).

### `castor add <PATH>...`

Add files or directories to the store.

```bash
castor add <PATH>... [--ref-name <NAME>]

Arguments:
  <PATH>...  One or more paths to add

Options:
  --ref-name <NAME>  Create a named reference to the added content
```

**Examples:**

```bash
# Add a single file
castor add document.pdf

# Add multiple files
castor add file1.txt file2.txt dir/

# Add with a reference
castor add project/ --ref-name release-v1.0
```

The command outputs the hash of each added object. Directories are added recursively and stored as tree objects.

### `castor materialize <HASH> <DEST>`

Materialize (restore) an object from the store to the filesystem.

```bash
castor materialize <HASH> <DEST>

Arguments:
  <HASH>  Hash of the object to materialize
  <DEST>  Destination path (must not exist)
```

**Examples:**

```bash
# Restore a directory
castor materialize abc123... ./restored-project

# Restore a file
castor materialize def456... ./document.pdf
```

### `castor cat <HASH>`

Output blob content to stdout.

```bash
castor cat <HASH>

Arguments:
  <HASH>  Hash of the blob
```

**Examples:**

```bash
# View a text file
castor cat abc123...

# Pipe to another command
castor cat abc123... | grep "search term"

# Save to a file
castor cat abc123... > output.txt
```

### `castor ls <HASH>`

List tree contents or show blob info.

```bash
castor ls <HASH> [--long]

Arguments:
  <HASH>  Hash of the object

Options:
  -l, --long  Show detailed information
```

**Examples:**

```bash
# List directory contents
castor ls abc123...

# Show detailed listing with modes and hashes
castor ls --long abc123...

# Output format (--long):
# b 100644 <hash> filename.txt
# t 040755 <hash> subdir
```

Type codes: `b` = blob (file), `t` = tree (directory)

### `castor stat <HASH>`

Show detailed metadata about an object.

```bash
castor stat <HASH>

Arguments:
  <HASH>  Hash of the object
```

**Example output:**

```
Hash: abc123...
Type: tree
Entries: 5
Size: 320 bytes (on disk)
Path: ./castor-store/objects/blake3-256/ab/c123...
```

### `castor gc`

Garbage collect unreferenced objects.

```bash
castor gc [--dry-run]

Options:
  --dry-run  Show what would be deleted without actually deleting
```

**Examples:**

```bash
# Preview what would be deleted
castor gc --dry-run

# Actually delete unreferenced objects
castor gc
```

Walks from all named references and deletes objects that are no longer reachable.

### `castor refs add <NAME> <HASH>`

Add a named reference to an object.

```bash
castor refs add <NAME> <HASH>

Arguments:
  <NAME>  Reference name
  <HASH>  Hash to reference
```

**Examples:**

```bash
castor refs add backup-2024 abc123...
castor refs add important def456...
```

References act as GC roots - objects reachable from references won't be deleted by `gc`.

### `castor refs list`

List all references.

```bash
castor refs list
```

**Example output:**

```
backup-2024 -> abc123...
important -> def456...
```

### `castor refs rm <NAME>`

Remove a reference.

```bash
castor refs rm <NAME>

Arguments:
  <NAME>  Reference name to remove
```

**Example:**

```bash
castor refs rm old-backup
```

## Global Options

All commands support these global options:

```bash
-r, --root <ROOT>  Store root directory
-h, --help         Print help
-V, --version      Print version
```

### Store Root Priority

The store root is determined in this order:

1. `--root` CLI argument
2. `CASTOR_ROOT` environment variable
3. `./castor-store` (default)

**Examples:**

```bash
# Use explicit root
castor --root /backup/store add myfile.txt

# Use environment variable
export CASTOR_ROOT=/backup/store
castor add myfile.txt

# Use default (./castor-store)
castor add myfile.txt
```

## Typical Workflows

### Backup Workflow

```bash
# Initialize store
castor init

# Create initial backup
castor add ~/important-data --ref-name backup-$(date +%Y%m%d)

# Add more data later
castor add ~/important-data --ref-name backup-$(date +%Y%m%d)

# List all backups
castor refs list

# Restore a backup
castor materialize <hash> ~/restored-data

# Clean up old backups
castor refs rm backup-20240101
castor gc
```

### Deduplication Example

```bash
# Add the same file twice
castor add file.txt
# Output: abc123...

castor add file.txt
# Output: abc123... (same hash - deduplicated!)

# Only one copy stored internally
```

### Exploring Content

```bash
# Add a directory
HASH=$(castor add myproject/ | awk '{print $1}')

# See what's in it
castor ls $HASH

# Look at a specific file
FILE_HASH=$(castor ls --long $HASH | grep "README.md" | awk '{print $3}')
castor cat $FILE_HASH
```

## Store Structure

```
castor-store/
├── config                    # Store configuration
├── objects/
│   └── blake3-256/          # Algorithm-specific directory
│       ├── ab/              # Shard directory (first 2 hex chars)
│       │   └── cd...ef      # Object file (remaining 62 hex chars)
│       └── ...
└── refs/                    # Named references
    ├── backup-2024
    └── important
```

## Object Types

- **Blob** - Raw file content
- **Tree** - Directory listing (sorted entries)

Trees reference other blobs and trees, forming a hierarchical structure similar to git.

## Exit Codes

- `0` - Success
- `1` - Error (with descriptive message to stderr)

## Environment Variables

- `CASTOR_ROOT` - Default store root directory

## Error Handling

All commands provide clear error messages:

```bash
$ castor cat invalid-hash
Error: Invalid hash: invalid-hash

$ castor add /nonexistent
Error: Failed to add path: /nonexistent
Caused by:
    No such file or directory (os error 2)
```

## Performance Tips

1. **Large files** - Content is streamed, not buffered in memory
2. **Many small files** - Use directories to group them
3. **Deduplication** - Identical content is stored only once
4. **GC frequency** - Run `gc` periodically to reclaim space from unreferenced objects

## Limitations

- **No compression** - Files stored as-is (MVP scope)
- **No encryption** - Store plaintext only
- **No network** - Local-only storage
- **No chunking** - Each file stored as single blob
- **POSIX only** - Full permission preservation only on Unix-like systems

## Comparison to Git

| Feature | Castor | Git |
|---------|--------|-----|
| Content addressing | ✓ | ✓ |
| Deduplication | ✓ | ✓ |
| Trees/Blobs | ✓ | ✓ |
| Hash algorithm | BLAKE3 | SHA-1/SHA-256 |
| Commits | ✗ | ✓ |
| Branches | ✗ | ✓ |
| Diffs | ✗ | ✓ |
| Network | ✗ | ✓ |
| Use case | File storage | Version control |

Castor is simpler than git - it's just content-addressed storage without the version control features.

## Troubleshooting

### Store not found

```bash
$ castor add file.txt
Error: Failed to open store at ./castor-store

# Solution: Initialize the store first
$ castor init
```

### Object not found

```bash
$ castor cat abc123...
Error: Object not found: abc123...

# Solution: Verify the hash is correct
$ castor refs list  # Find the correct hash
```

### Path already exists

```bash
$ castor materialize abc123... ./output
Error: Path already exists: ./output

# Solution: Remove the destination first or use a different path
$ rm -rf ./output
$ castor materialize abc123... ./output
```

## Development

```bash
# Run from source
cargo run -p castor -- <args>

# Build optimized binary
cargo build --release -p castor

# Run tests
cargo test -p castor

# Format code
cargo fmt -p castor

# Lint
cargo clippy -p castor
```

## License

See the workspace LICENSE file.

## See Also

- **castor_core** - The library powering this CLI
- **NOTES.md** - Design and specification
- **CLAUDE.md** - Development guidelines
