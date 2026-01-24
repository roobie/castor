# `casq`

A production-ready content-addressed file store CLI with compression and chunking (v0.4.0).

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
casq init

# Add files or directories
casq add myfile.txt
casq add mydir/

# Add content from stdin (pipe data directly)
curl https://example.org | casq add --ref-name example-dot-org@20260123 -
echo "quick note" | casq add --ref-name note-123 -

# Add with a named reference
casq add important-data/ --ref-name backup-2024

# Discover what content you have
casq ls              # Lists all references
casq ls --long       # With type info

# List tree contents
casq ls <hash>

# Output blob content
casq cat <hash>

# Show object metadata
casq stat <hash>

# Materialize (restore) to filesystem
casq materialize <hash> ./restored

# Garbage collect unreferenced objects
casq gc --dry-run  # Preview
casq gc            # Actually delete
```

## Commands

### `casq init`

Initialize a new content-addressed store.

```bash
casq init [--algo blake3]

Options:
  --algo <ALGORITHM>  Hash algorithm (default: blake3)
```

Creates the store directory structure at the configured root (default: `./casq-store`).

### `casq add <PATH>...` or `casq add -`

Add files, directories, or stdin content to the store.

```bash
casq add <PATH>... [--ref-name <NAME>]
casq add - [--ref-name <NAME>]

Arguments:
  <PATH>...  One or more paths to add
  -          Read content from stdin (cannot mix with filesystem paths)

Options:
  --ref-name <NAME>  Create a named reference to the added content
```

**Examples:**

```bash
# Add a single file
casq add document.pdf

# Add multiple files
casq add file1.txt file2.txt dir/

# Add with a reference
casq add project/ --ref-name release-v1.0

# Add from stdin
echo "Hello, World!" | casq add -
curl https://api.example.com/data | casq add --ref-name api-snapshot -
cat large-file.bin | casq add --ref-name binary-data -
```

The command outputs the hash of each added object. Directories are added recursively and stored as tree objects. Stdin content is stored as a blob.

**Important notes:**
- When using stdin (`-`), you cannot mix it with filesystem paths
- Stdin can only be specified once per invocation
- Output format for stdin: `<hash> (stdin)`

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

### `casq cat <HASH>`

Output blob content to stdout.

```bash
casq cat <HASH>

Arguments:
  <HASH>  Hash of the blob
```

**Examples:**

```bash
# View a text file
casq cat abc123...

# Pipe to another command
casq cat abc123... | grep "search term"

# Save to a file
casq cat abc123... > output.txt
```

### `casq ls [HASH]`

List references (if no hash), tree contents, or blob info.

```bash
casq ls [HASH] [--long]

Arguments:
  [HASH]  Hash of the object (optional - lists all refs if omitted)

Options:
  -l, --long  Show detailed information
```

**Examples:**

```bash
# List all references (discover what content you have)
casq ls

# List all references with type info
casq ls --long

# List directory contents
casq ls abc123...

# Show detailed listing with modes and hashes
casq ls --long abc123...

# Output format for refs:
# my-backup -> abc123...

# Output format for trees (--long):
# b 100644 <hash> filename.txt
# t 040755 <hash> subdir
```

Type codes: `b` = blob (file), `t` = tree (directory)

**Tip:** Use `casq ls` to discover content, then `casq ls <hash>` to explore it.

### `casq stat <HASH>`

Show detailed metadata about an object.

```bash
casq stat <HASH>

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

### `casq gc`

Garbage collect unreferenced objects.

```bash
casq gc [--dry-run]

Options:
  --dry-run  Show what would be deleted without actually deleting
```

**Examples:**

```bash
# Preview what would be deleted
casq gc --dry-run

# Actually delete unreferenced objects
casq gc
```

Walks from all named references and deletes objects that are no longer reachable.

### `casq refs add <NAME> <HASH>`

Add a named reference to an object.

```bash
casq refs add <NAME> <HASH>

Arguments:
  <NAME>  Reference name
  <HASH>  Hash to reference
```

**Examples:**

```bash
casq refs add backup-2024 abc123...
casq refs add important def456...
```

References act as GC roots - objects reachable from references won't be deleted by `gc`.

### `casq refs list`

List all references.

```bash
casq refs list
```

**Example output:**

```
backup-2024 -> abc123...
important -> def456...
```

### `casq refs rm <NAME>`

Remove a reference.

```bash
casq refs rm <NAME>

Arguments:
  <NAME>  Reference name to remove
```

**Example:**

```bash
casq refs rm old-backup
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
3. `./casq-store` (default)

**Examples:**

```bash
# Use explicit root
casq --root /backup/store add myfile.txt

# Use environment variable
export CASTOR_ROOT=/backup/store
casq add myfile.txt

# Use default (./casq-store)
casq add myfile.txt
```

## Typical Workflows

### Backup Workflow

```bash
# Initialize store
casq init

# Create initial backup
casq add ~/important-data --ref-name backup-$(date +%Y%m%d)

# Add more data later
casq add ~/important-data --ref-name backup-$(date +%Y%m%d)

# List all backups
casq refs list

# Restore a backup
casq materialize <hash> ~/restored-data

# Clean up old backups
casq refs rm backup-20240101
casq gc
```

### Deduplication Example

```bash
# Add the same file twice
casq add file.txt
# Output: abc123...

casq add file.txt
# Output: abc123... (same hash - deduplicated!)

# Only one copy stored internally
```

### Exploring Content

```bash
# Add a directory with a reference
casq add myproject/ --ref-name current-work

# Discover what's in your store
casq ls
# Output: current-work -> abc123...

# Explore the tree
HASH=$(casq ls | head -1 | awk '{print $3}')
casq ls $HASH

# Look at a specific file
FILE_HASH=$(casq ls --long $HASH | grep "README.md" | awk '{print $3}')
casq cat $FILE_HASH
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

- `CASTOR_ROOT` - Default store root directory

## Error Handling

All commands provide clear error messages:

```bash
$ casq cat invalid-hash
Error: Invalid hash: invalid-hash

$ casq add /nonexistent
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
casq --json init
casq --json add myfile.txt
casq --json ls
casq --json gc --dry-run

# Pipe through jq for processing
casq --json ls | jq '.refs[].name'
casq --json add file.txt | jq '.objects[0].hash'
```

### Standard Response Format

All JSON responses include these standard fields:
- `success` (boolean) - Whether the operation succeeded
- `result_code` (number) - Exit code (0 for success, non-zero for errors)

### Command-Specific Outputs

#### `init`
```json
{
  "success": true,
  "result_code": 0,
  "root": "/path/to/store",
  "algorithm": "blake3-256"
}
```

#### `add`
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

#### `ls` (refs list)
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

#### `ls <hash>` (tree contents)
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

#### `stat <hash>` (blob)
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

#### `gc`
```json
{
  "success": true,
  "result_code": 0,
  "dry_run": false,
  "objects_deleted": 42,
  "bytes_freed": 1048576
}
```

#### `orphans`
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

#### `journal`
```json
{
  "success": true,
  "result_code": 0,
  "entries": [
    {
      "timestamp": 1737556252,
      "timestamp_human": "2026-01-22T14:30:52Z",
      "operation": "add",
      "hash": "abc123...",
      "path": "/data",
      "metadata": "entries=15,size=1024"
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
# Extract hash from add operation
HASH=$(casq --json add data.txt | jq -r '.objects[0].hash')

# Count orphaned objects
COUNT=$(casq --json orphans | jq '.orphans | length')

# List all reference names
casq --json ls | jq -r '.refs[].name'

# Get GC stats
casq --json gc --dry-run | jq '{objects:.objects_deleted, bytes:.bytes_freed}'

# Check if operation succeeded
if casq --json add file.txt | jq -e '.success' > /dev/null; then
  echo "Success"
else
  echo "Failed"
fi

# Process journal entries
casq --json journal | jq -r '.entries[] | "\(.timestamp_human) \(.operation) \(.path)"'
```

### Exit Codes

Program exit codes match the `result_code` field in JSON output:
- `0` - Success
- `1` - Error (details in `error` field for JSON, or stderr for text)

### Binary Data Limitation

The `cat` command outputs binary data to stdout and cannot be used with `--json`. Use `materialize` or `stat` instead:

```bash
# This will error with JSON
casq --json cat <hash>  # Error: binary data incompatible with JSON

# Use these alternatives
casq --json materialize <hash> ./output  # Save to file
casq --json stat <hash>                  # Get metadata
```

## Limitations

- **No encryption** - Store plaintext only (planned for future)
- **No network** - Local-only storage
- **No parallel operations** - Single-threaded (may be added in future)
- **POSIX only** - Full permission preservation only on Unix-like systems

## Comparison to Git

| Feature | casq | Git |
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

casq is simpler than git - it's just content-addressed storage without the version control features.

## Troubleshooting

### Store not found

```bash
$ casq add file.txt
Error: Failed to open store at ./casq-store

# Solution: Initialize the store first
$ casq init
```

### Object not found

```bash
$ casq cat abc123...
Error: Object not found: abc123...

# Solution: Verify the hash is correct
$ casq refs list  # Find the correct hash
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
