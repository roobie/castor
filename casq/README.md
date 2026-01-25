# `casq`

A content-addressed file store CLI with compression and chunking (v0.4.0).

This is Alpha level software.

## Overview

**`casq`** is a command-line tool for managing content-addressed storage. It stores files and directories by their cryptographic hash, providing automatic deduplication, transparent compression, content-defined chunking, garbage collection, and named references.

This is the CLI binary that uses the `casq_core` library.

## Installation

```bash
# Build from source
cargo build --release -p casq

# The binary will be at target/release/casq
# Install it by
cargo install --path ./casq
# Optionally, copy to your PATH
cp target/release/casq $HOME/.local/bin/
```

## Quick Start

```bash
# Initialize a new store
casq initialize

# Add files or directories
casq put myfile.txt
casq put mydir/

# Add content from stdin (pipe data directly) - in most cases you want to use --reference
curl https://example.org | casq put --reference example-dot-org@20260123 -
echo "quick note" | casq put --reference note-123 -

# Add with a named reference
casq put important-data/ --reference backup-2024

# Discover what content you have
casq references list              # Lists all references

# List tree contents (requires hash)
casq list <hash>

# Output blob content
casq get <hash>

# Show object metadata
casq metadata <hash>

# Materialize (restore) to filesystem
casq materialize <hash> ./restored

# Garbage collect unreferenced objects
casq collect-garbage --dry-run  # Preview
casq collect-garbage            # Actually delete
```

## Commands

### `casq initialize`

Initialize a new content-addressed store.

```bash
casq initialize [--algorithm blake3]

Options:
  -a, --algorithm <ALGORITHM>  Hash algorithm (default: blake3)
```

Creates the store directory structure at the configured root (default: `./casq-store`).

### `casq put <PATH>` or `casq put -`

Add files, directories, or stdin content to the store.

```bash
casq put <PATH> [--reference <NAME>]
casq put - [--reference <NAME>]

Arguments:
  <PATH>  Path to add (a single file or directory), or
  -       Read content from stdin

Options:
  --reference <NAME>  Create a named reference to the added content
```

**Examples:**

```bash
# Add a single file
casq put document.pdf

# Add a directory
casq put project/

# Add with a reference
casq put project/ --reference release-v1.0

# Add from stdin
echo "Hello, World!" | casq put -
curl https://api.example.com/data | casq put --reference api-snapshot -
cat large-file.bin | casq put --reference binary-data -
```

The command outputs the hash of the added object. Directories are added recursively and stored as tree objects (and the returned hash is that of the tree itself). Stdin content is stored as a blob.

**Important notes:**
- Output format on stdout is: `<hash>`

### `casq materialize <HASH> <DEST>`

Materialize (restore) an object from the store to the filesystem.

```bash
casq materialize <HASH> <DEST>

Arguments:
  <HASH>  Hash of the object to materialize
  <DEST>  Destination path (must not exist)
```

**Examples:**

```bash
# Restore a directory
casq materialize abc123... ./restored-project

# Restore a file
casq materialize def456... ./document.pdf
```

### `casq get <HASH>`

Output blob content to stdout.

```bash
casq get <HASH>

Arguments:
  <HASH>  Hash of the blob
```

**Examples:**

```bash
# View a text file
casq get abc123...

# Pipe to another command
casq get abc123... | grep "search term"

# Save to a file
casq get abc123... > output.txt
```

### `casq list <HASH>`

List tree contents or show blob info.

```bash
casq list <HASH> [--long]

Arguments:
  <HASH>  Hash of the object (required)

Options:
  -l, --long  Show detailed information
```

**Examples:**

```bash
# List directory contents
casq list abc123...

# Show detailed listing with modes and hashes
casq list --long abc123...

# Output format (short):
# filename.txt
# subdir

# Output format (--long):
# b 100644 <hash> filename.txt
# t 040755 <hash> subdir
```

Type codes: `b` = blob (file), `t` = tree (directory)

**Tip:** Use `casq references list` to discover content, then `casq list <hash>` to explore it.

### `casq metadata <HASH>`

Show detailed metadata about an object.

```bash
casq metadata <HASH>

Arguments:
  <HASH>  Hash of the object
```

**Example output:**

```
Hash: abc123...
Type: tree
Entries: 5
Size: 320 bytes (on disk)
Path: ./casq-store/objects/blake3-256/ab/c123...
```

### `casq collect-garbage`

Garbage collect unreferenced objects.

```bash
casq collect-garbage [--dry-run]

Options:
  --dry-run  Show what would be deleted without actually deleting
```

**Examples:**

```bash
# Preview what would be deleted
casq collect-garbage --dry-run

# Actually delete unreferenced objects
casq collect-garbage
```

Walks from all named references and deletes objects that are no longer reachable.

### `casq references add <NAME> <HASH>`

Add a named reference to an object.

```bash
casq references add <NAME> <HASH>

Arguments:
  <NAME>  Reference name
  <HASH>  Hash to reference
```

**Examples:**

```bash
casq references add backup-2024 abc123...
casq references add important def456...
```

References act as GC roots - objects reachable from references won't be deleted by `collect-garbage`.

### `casq references list`

List all references.

```bash
casq references list
```

**Example output:**

```
backup-2024 -> abc123...
important -> def456...
```

### `casq references remove <NAME>`

Remove a reference.

```bash
casq references remove <NAME>

Arguments:
  <NAME>  Reference name to remove
```

**Example:**

```bash
casq references remove old-backup
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
2. `CASQ_ROOT` environment variable
3. `./casq-store` (default)

**Examples:**

```bash
# Use explicit root
casq --root /backup/store put myfile.txt

# Use environment variable
export CASQ_ROOT=/backup/store
casq put myfile.txt

# Use default (./casq-store)
casq put myfile.txt
```

## Output Streams

`casq` follows Unix conventions for output streams to enable proper pipeline usage:

**Text mode** (default):
- All informational messages, confirmations, and data → **stderr**
- **stdout** is empty
- This allows reliable pipeline usage and scripting

**JSON mode** (`--json` flag):
- All structured output → **stdout**
- Errors → **stderr** (as JSON)
- Designed for parsing and automation

**Examples:**

```bash
# Text mode - output on stderr
casq put file.txt                  # Extract hash
casq references list | grep myref  # Filter refs

# Suppress informational messages
casq initialize 2>/dev/null

# JSON mode - output on stdout (recommended for scripts)
HASH=$(casq --json put file.txt | jq -r '.object.hash')
casq --json references list | jq '.refs[].name
```

**For scripting**: Use `--json` flag for reliable, machine-readable output.

## Typical Workflows

### Backup Workflow

```bash
# Initialize store
casq initialize

# Create initial backup
casq put ~/important-data --reference backup-$(date +%Y%m%d)

# Add more data later
casq put ~/important-data --reference backup-$(date +%Y%m%d)

# List all backups
casq references list

# Restore a backup
casq materialize <hash> ~/restored-data

# Clean up old backups
casq references remove backup-20240101
casq collect-garbage
```

### Deduplication Example

```bash
# Add the same file twice
casq put file.txt
# Output: abc123...

casq put file.txt
# Output: abc123... (same hash - deduplicated!)

# Only one copy stored internally
```

### Exploring Content

```bash
# Add a directory with a reference
casq put myproject/ --reference current-work

# Discover what's in your store
casq references list
# Output: current-work -> abc123...

# Explore the tree
HASH=$(casq references list --json | jq '.[0].name')
casq list $HASH

# Look at a specific file
FILE_HASH=$(casq list --json --long $HASH | jq '.entries[] | select(.name == "README.md") | .hash' )
casq get $FILE_HASH
```

## Store Structure

```
casq-store/
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

- **Blob** - Raw file content (automatically compressed if ≥ 4KB)
- **Tree** - Directory listing (sorted entries)
- **ChunkList** - Large file split into chunks (files ≥ 1MB, enables incremental backups)

Trees reference other blobs and trees, forming a hierarchical structure similar to git. Large files are split into chunks for efficient incremental backups and cross-file deduplication.

## Exit Codes

- `0` - Success
- `1` - Error (with descriptive message to stderr)

## Environment Variables

- `CASQ_ROOT` - Default store root directory

## Error Handling

All commands provide clear error messages:

```bash
$ casq get invalid-hash
Error: Invalid hash: invalid-hash

$ casq put /nonexistent
Error: Failed to add path: /nonexistent
Caused by:
    No such file or directory (os error 2)
```

## Performance Tips

1. **Large files** - Content is streamed, not buffered in memory
2. **Many small files** - Use directories to group them
3. **Deduplication** - Identical content is stored only once (including chunk-level deduplication)
4. **Compression** - Files ≥ 4KB automatically compressed with zstd (3-5x typical reduction)
5. **Chunking** - Files ≥ 1MB split into chunks for incremental backups (change 1 byte → store ~512KB)
6. **GC frequency** - Run `gc` periodically to reclaim space from unreferenced objects

## Storage Efficiency (v0.4.0+)

- **Compression**: 3-5x reduction for text files, 2-3x for mixed data
- **Chunking**: Change 1 byte in 1GB file → store only ~512KB (changed chunk)
- **Cross-file deduplication**: Shared content across files stored only once
- **Example**: 10 files with identical 5MB section = 5MB stored (not 50MB)

## JSON Output

All commands support the `--json` flag for machine-readable output, enabling scripting and automation.

### Basic Usage

```bash
# Get JSON output from any command
casq --json initialize
casq --json put myfile.txt
casq --json references list
casq --json collect-garbage --dry-run

# Pipe through jq for processing
casq --json references list | jq '.refs[].name'
casq --json put file.txt | jq '.object.hash'
```

### Standard Response Format

All JSON responses include these standard fields:
- `success` (boolean) - Whether the operation succeeded
- `result_code` (number) - Exit code (0 for success, non-zero for errors)

### Command-Specific Outputs

#### `initialize`
```json
{
  "success": true,
  "result_code": 0,
  "root": "/path/to/store",
  "algorithm": "blake3-256"
}
```

#### `put`
```json
{
  "success": true,
  "result_code": 0,
  "objects": [
    {"hash": "abc123...", "path": "/path/to/file.txt"}
  ],
  "reference": {
    "name": "myref",
    "hash": "abc123..."
  }
}
```

#### `references list`
```json
{
  "success": true,
  "result_code": 0,
  "type": "RefList",
  "refs": [
    {"name": "backup", "hash": "abc123..."}
  ]
}
```

#### `list <hash>` (tree contents)
```json
{
  "success": true,
  "result_code": 0,
  "type": "TreeContents",
  "hash": "abc123...",
  "entries": [
    {
      "name": "file.txt",
      "entry_type": "blob",
      "mode": "100644",
      "hash": "def456..."
    }
  ]
}
```

#### `metadata <hash>` (blob)
```json
{
  "success": true,
  "result_code": 0,
  "type": "Blob",
  "hash": "abc123...",
  "size": 1024,
  "size_on_disk": 512,
  "path": "/store/objects/blake3-256/ab/c123..."
}
```

#### `collect-garbage`
```json
{
  "success": true,
  "result_code": 0,
  "dry_run": false,
  "objects_deleted": 42,
  "bytes_freed": 1048576
}
```

#### `find-orphans`
```json
{
  "success": true,
  "result_code": 0,
  "orphans": [
    {
      "hash": "abc123...",
      "entry_count": 15,
      "approx_size": 1024
    }
  ]
}
```

#### Error Response (stderr)
```json
{
  "success": false,
  "result_code": 1,
  "error": "Object not found: abc123..."
}
```

### Scripting Examples

```bash
# Extract hash from put operation
HASH=$(casq --json put data.txt | jq -r '.objects[0].hash')

# Count orphaned objects
COUNT=$(casq --json find-orphans | jq '.orphans | length')

# List all reference names
casq --json references list | jq -r '.refs[].name'

# Get GC stats
casq --json collect-garbage --dry-run | jq '{objects:.objects_deleted, bytes:.bytes_freed}'

# Check if operation succeeded
if casq --json put file.txt | jq -e '.success' > /dev/null; then
  echo "Success"
else
  echo "Failed"
fi
```

### Exit Codes

Program exit codes match the `result_code` field in JSON output:
- `0` - Success
- `1` - Error (details in `error` field for JSON, or stderr for text)

### Binary Data Limitation

The `get` command outputs binary data to stdout and cannot be used with `--json`. Use `materialize` or `metadata` instead:

```bash
# This will error with JSON
casq --json get <hash>  # Error: binary data incompatible with JSON

# Use these alternatives
casq --json materialize <hash> ./output  # Save to file
casq --json metadata <hash>              # Get metadata
```

## Limitations

- **No encryption** - Store plaintext only
- **No network** - Local-only storage
- **No parallel operations** - Single-threaded (may be added in future)
- **POSIX only** - Full permission preservation only on Unix-like systems

## Comparison to Git

| Feature            | casq         | Git             |
|--------------------|--------------|-----------------|
| Content addressing | ✓            | ✓               |
| Deduplication      | ✓            | ✓               |
| Trees/Blobs        | ✓            | ✓               |
| Hash algorithm     | BLAKE3       | SHA-1/SHA-256   |
| Commits            | ✗            | ✓               |
| Branches           | ✗            | ✓               |
| Diffs              | ✗            | ✓               |
| Network            | ✗            | ✓               |
| Use case           | File storage | Version control |

casq is simpler than git - it's just content-addressed storage without the version control features.

## Troubleshooting

### Store not found

```bash
$ casq put file.txt
Error: Failed to open store at ./casq-store

# Solution: Initialize the store first
$ casq initialize
```

### Object not found

```bash
$ casq get abc123...
Error: Object not found: abc123...

# Solution: Verify the hash is correct
$ casq references list  # Find the correct hash
```

### Path already exists

```bash
$ casq materialize abc123... ./output
Error: Path already exists: ./output

# Solution: Remove the destination first or use a different path
$ rm -rf ./output
$ casq materialize abc123... ./output
```

## Development

```bash
# Run from source
cargo run -p casq -- <args>

# Build optimized binary
cargo build --release -p casq

# Run tests
cargo test -p casq

# Format code
cargo fmt -p casq

# Lint
cargo clippy -p casq
```

## License

> Apache-2.0

## See Also

- [**casq_core**](https://crates.io/crates/casq_core) - The library powering this CLI
- **NOTES.md** - Design and specification
- **CLAUDE.md** - Development guidelines
