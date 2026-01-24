# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General rules

  **CRITICAL**: Documentation in all forms (files in repo, memories etc) MUST be kept updated and current as part of ANY code change. Documentation updates are NOT optional and are NOT deferred - they are completed in the SAME work session as the code implementation. See "Documentation Requirements" section below for detailed guidelines.

  Always prefer Serena MCP tools.

## Testing and Quality Assurance Plans

The project has dedicated implementation plans for advanced testing:

- **[PROPERTY_TESTING_PLAN.md](PROPERTY_TESTING_PLAN.md)** - Phase 1: Property-based testing (immediate focus)
- **[FUZZING_PLAN.md](FUZZING_PLAN.md)** - Future: Fuzzing strategy (deferred QA)

These plans provide detailed implementation strategies for achieving production-grade robustness.

## Documentation Requirements

**CRITICAL: All code changes MUST be accompanied by corresponding documentation updates BEFORE the work is considered complete.**

### Documentation Update Checklist

When implementing changes, you MUST update the relevant documentation files as part of the same work session:

1. **For ALL changes:**
   - Update `/workspace/CLAUDE.md` if project structure, architecture, or development guidelines change

2. **For new features or API changes:**
   - Update `/workspace/README.md` (main project overview)
   - Update `/workspace/casq_core/README.md` (if core library changes)
   - Update `/workspace/casq/README.md` (if CLI changes)
   - Update `/workspace/NOTES.md` (if design/architecture changes)

3. **For new tests or test infrastructure:**
   - Update `/workspace/casq-test/README.md` (test suite documentation)
   - Update `/workspace/TESTING.md` (testing guide)

4. **For implementation milestones:**
   - Create or update `/workspace/IMPLEMENTATION_SUMMARY.md` with details of what was implemented

### What Requires Documentation Updates

- ✅ **New features** - Add to feature lists in all READMEs
- ✅ **API changes** - Update API examples and signatures
- ✅ **New dependencies** - Update dependency lists in all READMEs
- ✅ **Architecture changes** - Update CLAUDE.md, NOTES.md, and relevant READMEs
- ✅ **New commands** - Update CLI documentation with examples
- ✅ **Performance characteristics** - Update performance sections
- ✅ **Object format changes** - Update format specifications
- ✅ **Test coverage changes** - Update test count and coverage sections
- ✅ **Limitations removed** - Update limitations sections
- ✅ **New modules** - Update module structure documentation

### Documentation Update Process

**DO NOT:**
- ❌ Implement a feature and say "documentation can be updated later"
- ❌ Skip documentation updates because they seem minor
- ❌ Update only one README when changes affect multiple areas
- ❌ Leave documentation with outdated version numbers, test counts, or feature lists

**DO:**
- ✅ Update documentation in the SAME session as code implementation
- ✅ Check ALL relevant README files for needed updates
- ✅ Verify version numbers, test counts, and statistics are current
- ✅ Update examples to use new features
- ✅ Remove outdated limitations when features are implemented
- ✅ Use TodoWrite to track documentation updates as separate tasks

### Example: Feature Implementation Flow

```
1. Implement feature code
2. Write/update tests
3. Verify tests pass
4. Update /workspace/README.md (if applicable)
5. Update /workspace/casq_core/README.md (if library changes)
6. Update /workspace/casq/README.md (if CLI changes)
7. Update /workspace/CLAUDE.md (if architecture/process changes)
8. Update /workspace/TESTING.md (if test infrastructure changes)
9. Verify all documentation is consistent
10. THEN mark work as complete
```

### Verification Before Completion

Before considering any work complete, verify:
- [ ] All relevant README files reviewed and updated
- [ ] Version numbers updated if applicable
- [ ] Test counts updated to match reality
- [ ] New features added to feature lists
- [ ] Examples updated to use new capabilities
- [ ] Removed limitations that are now implemented
- [ ] Architecture diagrams/descriptions updated if structure changed
- [ ] Dependencies lists current
- [ ] No references to "TODO" or "future work" for completed features

## Project Overview

**casq** (v0.4.0) is a content-addressed file store (CAS) - a production-ready, single-binary system for storing and retrieving files and directories by their cryptographic hash. Think "minimal git object store / restic backend" but with modern compression and chunking.

Key characteristics:
- Local-only, single-user, no network support
- Content-addressed storage: files/dirs stored by hash
- Immutable objects with stable content IDs
- Tree-based directory representation
- Garbage collection for unreferenced objects
- **Transparent zstd compression** (files ≥ 4KB automatically compressed)
- **Content-defined chunking** (files ≥ 1MB split into variable chunks for incremental backups)
- **Full backward compatibility** (v1 and v2 object formats coexist)

## Project Structure

This is a **Rust workspace** with two crates:

- `casq_core/`: Core library implementing the storage engine, hashing, compression, chunking, and object management
- `casq/`: CLI binary that provides the user interface

**Status:** Production-ready with comprehensive test coverage (120 unit tests, 266 integration tests).

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

## Architecture

### Storage Model

**Objects directory structure:**
```
$STORE_ROOT/
  config               # Store configuration (algorithm, version)
  journal              # Operation log (timestamp|operation|hash|path|metadata)
  objects/
    blake3-256/        # BLAKE3 hashing
      ab/
        abcd...        # Object files named by hash (may be compressed)
  refs/                # Named references to root hashes
    backup-name
```

**Object types:**
1. **Blob**: File content (automatically compressed if ≥ 4KB)
2. **Tree**: Directory structure (list of entries with mode, type, hash, name)
3. **ChunkList**: Large file split into chunks (files ≥ 1MB, enables incremental backups)

### On-Disk Format

**Object file header (16 bytes) - v2 (current):**
```
0x00  4   "CAFS" magic
0x04  1   version (u8) = 2
0x05  1   type: 1=blob, 2=tree, 3=chunk_list
0x06  1   algo: 1=blake3-256
0x07  1   compression: 0=none, 1=zstd
0x08  8   payload_len (u64 LE) - compressed size if compressed
0x10  ... payload (possibly compressed)
```

**Object file header (16 bytes) - v1 (legacy, still supported):**
```
0x00  4   "CAFS" magic
0x04  1   version (u8) = 1
0x05  1   type: 1=blob, 2=tree
0x06  1   algo: 1=blake3-256
0x07  1   reserved (must be 0)
0x08  8   payload_len (u64 LE)
0x10  ... payload (uncompressed)
```

**Tree entry format:**
```
0     1    type (u8): 1=blob, 2=tree
1     4    mode (u32 LE, POSIX)
5     32   hash (raw 32-byte digest)
37    1    name_len (u8)
38    N    name bytes (UTF-8)
```

**ChunkList entry format (40 bytes per chunk):**
```
0     32   chunk_hash (BLAKE3 of chunk content)
32    8    chunk_size (u64 LE)
```

### CLI Commands

```bash
casq init [--root PATH] [--algo blake3]
casq add PATH... [--ref-name NAME]
casq add - [--ref-name NAME]  # Read from stdin (use "-" as path)
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

### Stdin Support

**casq** supports reading content directly from stdin using the `-` argument:

```bash
# Pipe curl output
curl https://example.org | casq add --ref-name example-dot-org@20260123 -

# Pipe echo output
echo "quick note" | casq add --ref-name note-123 -

# Pipe any command
cat large-file.bin | casq add -
```

**Features:**
- Stdin content is stored as a blob (automatically compressed/chunked based on size)
- Output format: `<hash> (stdin)`
- Journal entries use `"(stdin)"` as the path
- Cannot mix stdin with filesystem paths in the same command
- Stdin can only be specified once per invocation

**Error handling:**
- TTY detection prevents accidental stdin usage without pipe
- Clear error messages for invalid usage patterns

**Examples:**

```bash
# Basic stdin
$ echo "Hello World" | casq add -
af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262 (stdin)

# With reference
$ curl https://api.example.com/data | casq add --ref-name api-snapshot -
abc123... (stdin)
Created reference: api-snapshot -> abc123...

# Journal entry
$ casq journal --recent 1
2026-01-23 10:30:00  add  abc123...  (stdin)  entries=1,size=512
```

### JSON Output (v0.6.0+)

**casq** supports machine-readable JSON output via the `--json` global flag, enabling scripting and automation.

**Usage:**
```bash
# All commands support --json
casq --json init
casq --json add myfile.txt
casq --json ls
casq --json gc --dry-run

# Pipe through jq for processing
casq --json ls | jq '.refs[].name'
casq --json add file.txt | jq '.objects[0].hash'
```

**Standard Response Format:**

All JSON responses include:
- `success: bool` - Whether the operation succeeded
- `result_code: u8` - Exit code (0 for success, non-zero for errors)
- Command-specific fields (hashes, counts, paths, etc.)

**Example Outputs:**

```json
// init
{"success":true,"result_code":0,"root":"./casq-store","algorithm":"blake3-256"}

// add with reference
{"success":true,"result_code":0,"objects":[{"hash":"abc123...","path":"file.txt"}],"reference":{"name":"backup","hash":"abc123..."}}

// ls (refs)
{"success":true,"result_code":0,"type":"RefList","refs":[{"name":"backup","hash":"abc123..."}]}

// gc
{"success":true,"result_code":0,"dry_run":false,"objects_deleted":42,"bytes_freed":1048576}

// Error (stderr)
{"success":false,"result_code":1,"error":"Object not found: abc123..."}
```

**Implementation:**
- Output abstraction layer in `casq/src/output.rs`
- DTOs (Data Transfer Objects) for all command responses
- Serde serialization with custom `Hash` serializer (outputs hex string)
- Error responses on stderr in JSON mode
- Exit codes match `result_code` in JSON

**Binary Data Limitation:**
- `cat` command errors in JSON mode (binary data incompatible with JSON)
- Use `materialize` or `stat` as alternatives

**Testing:**
- 26 integration tests in `casq-test/tests/test_json_output.py`
- Full backward compatibility verified (all existing tests pass)

### Dependencies

**casq_core:**
- `blake3`: BLAKE3 cryptographic hashing
- `hex`: Hash hex encoding/decoding
- `tempfile`: Atomic object writes
- `ignore`: Filesystem walking with .gitignore support
- `thiserror`: Error definitions
- `serde`: Serialization for JSON output (v0.6.0+)
- `zstd`: Transparent zstd compression (v0.4.0+)
- `fastcdc`: Content-defined chunking (v0.4.0+)

**casq:**
- `casq_core`: The core library
- `clap`: CLI argument parsing with derive macros
- `anyhow`: Error handling in main
- `atty`: TTY detection for stdin validation
- `serde`: Serialization support (v0.6.0+)
- `serde_json`: JSON serialization (v0.6.0+)

## Design Principles

1. **Content-addressed**: Objects are immutable and identified by hash
2. **Simple format**: Binary format with clear headers, human-inspectable
3. **Canonical hashing**: Tree entries sorted by name for stable hashes
4. **Garbage collection**: Unreferenced objects removed via reachability analysis from refs
5. **Transparent optimization**: Compression and chunking automatic, invisible to API consumers
6. **Backward compatibility**: v1 objects remain readable, no migration required
7. **Efficient storage**: 3-5x compression for typical data, incremental backups via chunking
8. **Local-only**: No network features, encryption, or multi-user support (by design)

## Implementation Notes

### Compression and Chunking (v0.4.0+)

**Compression (Transparent):**
- **Threshold**: Files/blobs ≥ 4KB are automatically compressed with zstd (level 3)
- **Algorithm**: Zstandard (fast compression ~500 MB/s, 3-5x typical reduction)
- **Hash stability**: Hashes always computed on **uncompressed** data
- **Trees**: Not compressed (typically small metadata)

**Chunking (Content-Defined):**
- **Threshold**: Files ≥ 1MB are split into variable-size chunks using FastCDC
- **Chunk sizes**: Min 256KB, Average 512KB, Max 1MB
- **Storage**: Chunks stored as regular blobs (with compression if ≥ 4KB)
- **ChunkList object**: Contains array of (chunk_hash, chunk_size) pairs
- **Benefits**: Incremental backups (change 1 byte → store ~1 chunk), cross-file deduplication

**Behavior:**
- Files < 4KB: Stored uncompressed as Blob
- Files 4KB - 1MB: Compressed Blob (v2 format)
- Files ≥ 1MB: ChunkList pointing to compressed chunks

### Implementation Workflow

When implementing new features:

1. **Planning Phase:**
   - Identify which documentation files will need updates
   - Add documentation update tasks to TodoWrite list

2. **Implementation Phase:**
   - Write code
   - Write/update tests
   - Run tests to verify

3. **Documentation Phase (REQUIRED BEFORE COMPLETION):**
   - Update all identified documentation files
   - Verify consistency across all documentation
   - Check for outdated references
   - Update version numbers and statistics

4. **Verification Phase:**
   - Run full test suite
   - Review all documentation changes
   - Ensure no "TODO" markers for completed work
   - Mark work as complete only after documentation is updated

**Remember: Documentation is not optional. Code without documentation updates is incomplete work.**

### Hashing Rules
- **Blob hash**: `hash = blake3(uncompressed_payload_bytes)` (payload only, not header)
- **ChunkList hash**: `hash = blake3(original_file_bytes)` (not the ChunkList metadata)
- **Tree hash**: Hash of canonicalized entries (sorted by name)
- Object file path: `objects/<algo>/<first2hexchars>/<remaining60hexchars>`
- **Important**: Hashes are stable regardless of compression/chunking

### Tree Canonicalization
1. Collect all entries from filesystem
2. Sort by name (bytewise UTF-8)
3. Serialize according to tree entry format
4. Hash the serialized payload

### Refs and GC
- Refs stored as text files in `refs/` directory
- Each ref file contains hex hash (one per line, last non-empty line is current)
- GC walks from all ref roots, marks reachable objects (including chunks referenced by ChunkLists)
- Unreferenced objects deleted during sweep phase

## Current Implementation Status

### Core Features (v0.6.0)

**Storage Engine:**
- ✅ Content-addressed storage with BLAKE3 hashing
- ✅ Three object types: Blob, Tree, ChunkList
- ✅ Transparent zstd compression (files ≥ 4KB)
- ✅ Content-defined chunking with FastCDC (files ≥ 1MB)
- ✅ Atomic object writes with tempfile
- ✅ Hash-based deduplication (including chunk-level deduplication)

**Object Format:**
- ✅ v2 format with compression support
- ✅ Full backward compatibility with v1 objects
- ✅ Lazy migration (no data migration required)
- ✅ Mixed v1/v2 stores supported

**Commands:**
- ✅ `init` - Initialize new store
- ✅ `add` - Add files/directories to store (supports stdin with `-`)
- ✅ `materialize` - Restore files from store
- ✅ `cat` - Output blob content to stdout
- ✅ `ls` - List tree contents
- ✅ `stat` - Show object metadata
- ✅ `gc` - Garbage collection (handles all three object types)
- ✅ `orphans` - Find unreferenced tree roots
- ✅ `journal` - View operation history
- ✅ `refs` - Manage named references
- ✅ `--json` - JSON output for all commands (v0.6.0+)

**Test Coverage:**
- ✅ 120 Rust unit tests (100% pass rate)
- ✅ 292 Python integration tests (including 26 JSON output tests)
- ✅ Compression threshold tests
- ✅ Chunking boundary tests
- ✅ Round-trip integrity tests
- ✅ Deduplication tests (whole files and chunks)
- ✅ GC correctness with all object types
- ✅ Backward compatibility tests
- ✅ JSON output format tests

**Module Organization:**
- `casq_core/src/lib.rs` - Library exports
- `casq_core/src/hash.rs` - BLAKE3 hashing (with Serialize support)
- `casq_core/src/object.rs` - Object types and encoding (~350 lines)
- `casq_core/src/store.rs` - Storage engine with compression/chunking (~500 lines)
- `casq_core/src/chunking.rs` - FastCDC integration (~150 lines)
- `casq_core/src/tree.rs` - Tree utilities
- `casq_core/src/gc.rs` - Garbage collection (with Serialize support)
- `casq_core/src/walk.rs` - Filesystem walking
- `casq_core/src/journal.rs` - Operation journal
- `casq_core/src/error.rs` - Error types
- `casq/src/main.rs` - CLI implementation
- `casq/src/output.rs` - JSON output abstraction and DTOs (~300 lines)

### Known Limitations (By Design)

- No encryption at rest (deferred to future versions)
- No parallel operations (single-threaded)
- No remote backends (local-only by design)
- No object caching (direct disk I/O)
- No partial tree retrieval (materialize entire trees only)
- No snapshot abstractions (use refs for now)

### Storage Performance

**Typical compression ratios:**
- Text files: 3-5x reduction
- Binary data: 2-3x reduction
- Already compressed (images, video): minimal overhead (~2% header)

**Incremental backup efficiency:**
- Before chunking: 1GB file + 1 byte change = 2GB stored
- After chunking: 1GB file + 1 byte change = 1GB + ~512KB stored (one chunk)

**Chunk deduplication:**
- Shared content across files stored only once
- Example: 10 files with identical 5MB section = 5MB stored (not 50MB)

---

## IMPORTANT: Keeping This Document Current

When you implement changes to casq:

1. **Immediately update this CLAUDE.md file** with any architectural, structural, or procedural changes
2. **Update the "Current Implementation Status" section** when features are added or test counts change
3. **Update "Known Limitations"** when limitations are removed or new ones are identified
4. **Update "Module Organization"** when files are added, removed, or significantly restructured
5. **Update examples and documentation** to reflect new capabilities

**This document is a living guide - it must evolve with the codebase. Stale documentation is worse than no documentation.**
