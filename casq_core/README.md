# casq_core

A content-addressed file store (CAS) library using BLAKE3 hashing.

## Overview

`casq_core` is a Rust library that provides the core functionality for **casq**, a minimal, single-binary content-addressed storage system. It stores files and directories by their cryptographic hash, ensuring immutable, deduplicated storage with built-in garbage collection.

Think of it as a minimal git object store or restic backend, but generic and simple.

## Features

- ✅ **Content-Addressed Storage** - Files and directories stored by BLAKE3 hash
- ✅ **Automatic Deduplication** - Identical content stored only once
- ✅ **Tree-Based Directories** - Canonical ordering ensures stable hashes
- ✅ **Atomic Operations** - Tempfile-based writes prevent corruption
- ✅ **Garbage Collection** - Mark & sweep algorithm from reference roots
- ✅ **Corruption Detection** - Hash verification on all reads
- ✅ **Named References** - GC roots for preserving important snapshots
- ✅ **Full Round-Trip** - Add → Store → GC → Materialize
- ✅ **Cross-Platform** - Unix permissions preserved, Windows supported
- ✅ **Gitignore Support** - Respects `.gitignore` during filesystem walks

## Quick Start

```rust
use casq_core::{Store, Algorithm};
use std::path::Path;

// Initialize a new store
let store = Store::init("./my-store", Algorithm::Blake3)?;

// Add a file or directory
let hash = store.add_path(Path::new("./my-data"))?;

// Create a named reference (GC root)
store.refs().add("backup-2024", &hash)?;

// Garbage collect unreferenced objects
let stats = store.gc(false)?;
println!("Deleted {} objects, freed {} bytes",
         stats.objects_deleted, stats.bytes_freed);

// Materialize back to filesystem
store.materialize(&hash, Path::new("./restored"))?;
```

## Architecture

### Storage Format

Objects are stored with a 16-byte header followed by the payload:

```
0x00  4   "CAFS" magic
0x04  1   version (u8)
0x05  1   type: 1=blob, 2=tree
0x06  1   algo: 1=blake3-256
0x07  1   reserved (must be 0)
0x08  8   payload_len (u64 LE)
0x10  ... payload
```

### Directory Structure

```
$STORE_ROOT/
  config               # Store configuration (version, algorithm)
  objects/
    blake3-256/        # Algorithm-specific directory
      ab/              # First 2 hex chars (shard)
        abcd...ef      # Remaining 62 hex chars (object file)
  refs/                # Named references (GC roots)
    backup-name
```

### Object Types

1. **Blob** - Raw file content (hash of payload only)
2. **Tree** - Directory structure (sorted entries by name for canonical hashing)

### Module Structure

```
casq_core/src/
├── lib.rs       - Public API and documentation
├── error.rs     - Error types with thiserror
├── hash.rs      - BLAKE3 hashing (32-byte digests)
├── object.rs    - Binary object encoding/decoding
├── store.rs     - Store management and object I/O
├── tree.rs      - Tree entry encoding with canonical sorting
├── walk.rs      - Filesystem traversal with gitignore
├── gc.rs        - Garbage collection (mark & sweep)
└── refs.rs      - Reference management
```

## Building and Testing

```bash
# Build the library
cargo build --release -p casq_core

# Run all tests (68 unit tests + 1 doctest)
cargo test -p casq_core

# Run with output
cargo test -p casq_core -- --nocapture

# Check code quality
cargo clippy -p casq_core -- -D warnings

# Format code
cargo fmt -p casq_core
```

## API Overview

### Core Types

- `Store` - Main store interface
- `Hash` - 32-byte BLAKE3 hash wrapper
- `TreeEntry` - File/directory entry in a tree
- `RefManager` - Manages named references
- `GcStats` - Garbage collection statistics

### Main Operations

```rust
// Store initialization
let store = Store::init(path, Algorithm::Blake3)?;
let store = Store::open(path)?;

// Object storage
let hash = store.put_blob(reader)?;
let hash = store.put_tree(entries)?;
let hash = store.add_path(path)?;  // Recursively add file/dir

// Object retrieval
let data = store.get_blob(&hash)?;
let entries = store.get_tree(&hash)?;
store.cat_blob(&hash, writer)?;

// Materialization
store.materialize(&hash, dest_path)?;

// References
store.refs().add(name, &hash)?;
let hash = store.refs().get(name)?;
let all_refs = store.refs().list()?;
store.refs().remove(name)?;

// Garbage collection
let stats = store.gc(dry_run)?;
```

## Design Principles

1. **Content-Addressed** - Objects are immutable and identified by hash
2. **Canonical Hashing** - Tree entries sorted by name for stable hashes
3. **Atomic Writes** - Use tempfile for corruption-free operations
4. **Simple Format** - Binary format with clear headers, human-inspectable paths
5. **Minimal Dependencies** - Only essential crates (blake3, hex, tempfile, ignore, thiserror)
6. **No Network** - Local-only, single-user design (MVP scope)

## Hashing Rules

- **Blob hash**: `hash = blake3(payload_bytes)` (payload only, not header)
- **Tree hash**: Hash of canonicalized entries (sorted by name, bytewise UTF-8)
- **Object path**: `objects/<algo>/<prefix>/<suffix>` where prefix is first 2 hex chars

## Garbage Collection

- **Refs** are GC roots stored in `refs/` directory
- **Mark phase** traverses from all refs, recursively following tree entries
- **Sweep phase** deletes objects not in the reachable set
- **Dry-run mode** available for safe preview before deletion

## Test Coverage

```
✓ 68 unit tests passing
✓ 1 doctest passing
✓ 100% core functionality coverage
✓ Edge cases: corruption, empty files/dirs, large files, permissions
✓ Round-trip testing: add → store → materialize → verify
```

### Test Categories

- **Hash operations** - Encoding, decoding, validation
- **Object encoding** - Headers, payload, corruption detection
- **Store operations** - Init, open, blob/tree storage
- **Tree operations** - Canonical ordering, nested structures
- **Filesystem walking** - Files, directories, permissions, gitignore
- **References** - CRUD operations, validation
- **Garbage collection** - Mark, sweep, dry-run, tree reachability
- **Materialization** - Blobs, trees, nested structures, permissions

## Limitations (MVP Scope)

The following are intentionally **not supported** in the current MVP:

- ❌ Network operations (remote stores)
- ❌ Multi-user/concurrent access
- ❌ Content chunking or deduplication
- ❌ Compression
- ❌ Encryption
- ❌ Symbolic links
- ❌ Special file types (devices, sockets, etc.)
- ❌ Extended attributes or ACLs beyond basic POSIX permissions

## Performance Characteristics

- **Hash algorithm**: BLAKE3 (fast, cryptographically secure)
- **I/O**: Streaming for large files (no full buffering)
- **Deduplication**: Automatic via content addressing
- **GC**: Mark & sweep with efficient hash set operations
- **Directory sharding**: First 2 hex chars prevent filesystem bottlenecks

## Error Handling

All operations return `Result<T, Error>` with detailed error types:

- `IoError` - File system operations
- `CorruptedObject` - Hash mismatch or invalid format
- `InvalidHash` - Malformed hash string
- `ObjectNotFound` - Missing object in store
- `InvalidStore` - Store not initialized or corrupted config
- `InvalidRef` - Bad reference name or format
- `PathExists` - Destination already exists (materialization)

## Dependencies

```toml
blake3 = "1.5"      # BLAKE3 hashing
hex = "0.4"         # Hash hex encoding/decoding
tempfile = "3.0"    # Atomic object writes
ignore = "0.4"      # Filesystem walking with .gitignore support
thiserror = "2.0"   # Error handling
```

## Contributing

This library is part of the **casq** project. When contributing:

1. Ensure all tests pass: `cargo test -p casq_core`
2. Maintain clippy cleanliness: `cargo clippy -p casq_core -- -D warnings`
3. Format code: `cargo fmt -p casq_core`
4. Add tests for new functionality
5. Update documentation

## License

> Apache-2.0

## See Also

- [**casq**](https://crates.io/crates/casq) - CLI binary using this library
- **NOTES.md** - Detailed design and specification
- **CLAUDE.md** - Development guidelines for AI assistants
