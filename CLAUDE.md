# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General rules

  Documentation in all forms (files in repo, memories etc) must be kept updated and current.
  Always prefer Serena MCP tools.

## Project Overview

**casq** is a content-addressed file store (CAS) - a minimal, single-binary system for storing and retrieving files and directories by their cryptographic hash. Think "minimal git object store / restic backend" but generic and simple.

Key characteristics:
- Local-only, single-user, no network support
- Content-addressed storage: files/dirs stored by hash
- Immutable objects with stable content IDs
- Tree-based directory representation
- Garbage collection for unreferenced objects

## Project Structure

This is a **Rust workspace** with two crates:

- `casq_core/`: Core library implementing the storage engine, hashing, and object management
- `casq/`: CLI binary that provides the user interface

The project is in **early development** - both crates currently contain only "Hello, world!" placeholder code.

## Build and Development Commands

### Building
```bash
# Build the entire workspace
cargo build

# Build release version
cargo build --release

# Build specific crate
cargo build -p casq
cargo build -p casq_core
```

### Running
```bash
# Run the CLI (once implemented)
cargo run -p casq -- <args>

# Or after building
./target/debug/casq <args>
```

### Testing
```bash
# Run all tests
cargo test

# Run tests for specific crate
cargo test -p casq_core
cargo test -p casq

# Run with output
cargo test -- --nocapture
```

### Linting and Formatting
```bash
# Check code formatting
cargo fmt --check

# Format code
cargo fmt

# Run clippy
cargo clippy

# Run clippy with strict checks
cargo clippy -- -D warnings
```

## Planned Architecture

Based on NOTES.md, the system will implement:

### Storage Model

**Objects directory structure:**
```
$STORE_ROOT/
  config               # Store configuration (algorithm, version)
  journal              # Operation log (timestamp|operation|hash|path|metadata)
  objects/
    blake3/           # Initially using BLAKE3 hashing (via xxhash-rust for now)
      ab/
        abcd...       # Object files named by hash
  refs/               # Named references to root hashes
    backup-name
```

**Object types:**
1. **Blob**: Raw file content
2. **Tree**: Directory structure (list of entries with mode, type, hash, name)

### On-Disk Format

**Object file header (16 bytes):**
```
0x00  4   "CAFS" magic
0x04  1   version (u8)
0x05  1   type: 1=blob, 2=tree
0x06  1   algo: 1=blake3-256
0x07  1   reserved
0x08  8   payload_len (u64 LE)
0x10  ... payload
```

**Tree entry format:**
```
0     1    type (u8): 1=blob, 2=tree
1     4    mode (u32 LE, POSIX)
5     32   hash (raw 32-byte digest)
37    1    name_len (u8)
38    N    name bytes (UTF-8)
```

### CLI Commands

```bash
casq init [--root PATH] [--algo blake3]
casq add PATH... [--ref-name NAME]
casq materialize HASH DEST
casq cat HASH          # Output blob to stdout
casq ls HASH [--long]  # List tree contents or show blob info
casq stat HASH         # Show object metadata
casq gc [--dry-run]    # Garbage collect unreferenced objects
casq orphans [--long]  # Find orphaned tree roots (unreferenced trees)
casq journal [--recent N] [--orphans]  # View operation journal
casq refs add NAME HASH
casq refs list
casq refs rm NAME
```

### New Features: Orphan Discovery

**Problem:** When running `casq add /path` without `--ref-name`, the tree hash is printed but not stored. These objects become orphaned and will be deleted by GC.

**Solutions:**

1. **`casq orphans` command** - Discover unreferenced tree roots on-demand:
   - Identifies trees that exist in the store but have no references
   - Filters out child trees (only shows top-level orphan roots)
   - Use `--long` for detailed information

   ```bash
   $ casq orphans
   abc123def...  15 entries
   def456abc...  3 entries

   $ casq orphans --long
   Hash: abc123def456...
   Type: tree
   Entries: 15
   Approx size: 1024 bytes
   ---
   ```

2. **Operation Journal** - Automatically tracks `add` operations:
   - Records timestamp, hash, original path, and metadata for each `add`
   - Stored in `$STORE_ROOT/journal` as append-only text file
   - Use `casq journal --orphans` to find orphaned entries with context

   ```bash
   $ casq journal --recent 10
   2026-01-22 14:30:52  add  abc123def...  /important/data  entries=15,size=1024

   $ casq journal --orphans
   2026-01-22 14:30:52  add  abc123def...  /important/data  entries=15,size=1024
   ```

**Workflow:**
```bash
# User adds path but forgets to create ref
$ casq add /important/data
abc123def...  /important/data

# Later: discover orphans with context
$ casq journal --orphans
2026-01-22 14:30:52  add  abc123def...  /important/data  entries=15,size=1024

# Inspect before saving
$ casq ls abc123def...
file1.txt
file2.txt
subdir/

# Create ref to save it
$ casq refs add important-data abc123def...
```

### Dependencies

**casq_core:**
- `xxhash-rust` (xxh3): Fast hashing (placeholder; may switch to BLAKE3)
- `serde/serde_json`: Serialization
- `ignore`: Filesystem walking with .gitignore support
- `chrono`: Timestamp handling
- `thiserror`: Error definitions

**casq:**
- `casq_core`: The core library
- `clap`: CLI argument parsing with derive macros
- `anyhow`: Error handling in main
- `serde/serde_json`: For any JSON output

## Design Principles

1. **Content-addressed**: Objects are immutable and identified by hash
2. **Simple format**: Binary format with clear headers, human-inspectable
3. **Canonical hashing**: Tree entries sorted by name for stable hashes
4. **Garbage collection**: Unreferenced objects removed via reachability analysis from refs
5. **Minimal MVP scope**: No chunking, compression, encryption, or network support initially

## Implementation Notes

### Hashing Rules
- **Blob hash**: `hash = blake3(payload_bytes)` (payload only, not header)
- **Tree hash**: Hash of canonicalized entries (sorted by name)
- Object file path: `objects/<algo>/<first2hexchars>/<remaining60hexchars>`

### Tree Canonicalization
1. Collect all entries from filesystem
2. Sort by name (bytewise UTF-8)
3. Serialize according to tree entry format
4. Hash the serialized payload

### Refs and GC
- Refs stored as text files in `refs/` directory
- Each ref file contains hex hash (one per line, last non-empty line is current)
- GC walks from all ref roots, marks reachable objects, deletes unreachable
