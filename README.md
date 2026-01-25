# `casq`

![casq logo](assets/logo.jpeg)

**A content-addressed file store with compression and chunking.**

This is Alpha level software.

`casq` (v0.4.0) is a single-binary tool for storing files and directories by their cryptographic hash. Think of it as a lightweight git object store or restic backend—but simpler, local-only, and purpose-built for content-addressed storage with modern efficiency features.

**Why `casq`?**
- **Automatic deduplication** - Identical content stored only once, even across different directories
- **Transparent compression** - 3-5x storage reduction with zstd (files ≥ 4KB automatically compressed)
- **Content-defined chunking** - Incremental backups with FastCDC (files ≥ 1MB split into variable chunks)
- **Content addressing** - Files identified by cryptographic hash, not by path
- **Stdin support** - Pipe data directly from commands (e.g., `curl | casq put -`)
- **Garbage collection** - Reclaim space from unreferenced objects with mark & sweep
- **Simple & fast** - No databases, no network, just files on disk with BLAKE3 hashing
- **Embeddable** - Rust library (`casq_core`) + CLI binary, easily integrated into your tools

## Quick Start

```bash
# Initialize a store
casq initialize

# Add files and directories (automatically deduplicated)
casq put myproject/ --reference snapshot-2024-01-21

# Add content from stdin (pipe data directly)
curl https://example.org | casq put --reference example-dot-org@20260123 -
echo "quick note" | casq put --reference note-123 -

# List what you have
casq references list
# Output: snapshot-2024-01-21 -> abc123...

# Explore a tree
casq list abc123...

# Retrieve content
casq get <hash>                    # Stream a file to stdout
casq materialize abc123... ./out   # Restore entire directory

# Clean up unreferenced objects
casq collect-garbage --dry-run     # Preview
casq collect-garbage               # Actually delete
```

### JSON Output for Automation

All commands support `--json` flag for machine-readable output:

```bash
# Get structured output for scripting
casq --json initialize
# {"success":true,"result_code":0,"root":"./casq-store","algorithm":"blake3-256"}

# Pipe through jq for processing
casq --json references list | jq '.refs[].name'
casq --json put myfile.txt | jq '.objects[0].hash'
casq --json metadata <hash> | jq '{type:.type,size:.size}'

# Use in scripts for automation
HASH=$(casq --json put data.txt | jq -r '.objects[0].hash')
casq --json collect-garbage --dry-run | jq '{dry_run,objects:.objects_deleted,bytes:.bytes_freed}'
```

**All JSON responses include**:
- `success` (boolean) - Whether the operation succeeded
- `result_code` (number) - Exit code (0 for success, non-zero for errors)
- Command-specific fields (hashes, counts, paths, etc.)

See [CLI README](casq/README.md) for complete JSON output specification.

### Output Streams

`casq` follows Unix conventions for output streams:

- **Text mode**: Data and informational messages go to stderr, stdout is empty
  - This enables proper pipeline usage
  - Example: `HASH=$(casq put file.txt 2>&1 | awk '{print $1}')`

- **JSON mode**: All structured data goes to stdout
  - Designed for parsing and automation
  - Example: `HASH=$(casq --json add file.txt | jq -r '.objects[0].hash')`

This design allows you to:
```bash
# Pipe casq output reliably in text mode
casq references list 2>&1 | grep myref

# Suppress informational messages
casq initialize 2>/dev/null

# Extract data in JSON mode (recommended for scripts)
casq --json put file.txt | jq -r '.objects[0].hash'
```

**For scripting**: Use `--json` flag for reliable, structured output on stdout.

## Use Cases

### Developer & Build Workflows

- **Deterministic build cache**
  - Cache compile artifacts, test outputs, generated code by content hash.
  - Works across branches and directories since keys are content, not paths.
  - Very similar to Bazel/Nix-style caching, but lightweight and embeddable.

- **Incremental task runner**
  - Tools (linters, formatters, code generators) can skip work if input trees’ hashes already exist.
  - Ideal for CLI tools that need a simple, robust “don’t redo work” mechanism without designing a new cache format.

- **Hermetic snapshotting of inputs**
  - Capture exact versions of dependency trees or config directories by content hash.
  - Makes it easy to reproduce a build or run by just referring to a single tree hash.

### Backup, Snapshots & Sync (Local-Only)

- **Deduplicated local backups**
  - Back up project folders, config dirs, photos, etc. to a single store.
  - Cross-directory and cross-snapshot deduplication comes “for free” via hashing.
  - GC lets you drop old snapshots by removing root refs.

- **“Poor man’s” restic/borg without remote**
  - Use it as a backend for personal snapshot tools where you don’t need remote storage.
  - Just store named roots (labels for tree hashes) + the object store.

- **Local folder versioning**
  - Periodically ingest a directory tree and keep a timeline of root hashes.
  - Very cheap incremental snapshots: unchanged files share the same blobs.

### Data & Content Pipelines

- **Content-addressed artifact registry**
  - Store ML models, dataset shards, media assets, or compiled binaries addressed by hash.
  - Consumers can pin exact versions by hash, without designing a full packaging system.

- **ETL / data pipeline stage cache**
  - Cache outputs of expensive stages (e.g. preprocessed datasets) as trees.
  - If the input tree hash and the transformation code hash match, reuse cached output.

- **Immutable data lake on local disk**
  - For small to mid-size workloads, treat the store as a mini “data lake” of immutable, hashed blobs/trees.
  - Higher layers track which root hashes form a dataset / experiment.

### Application-Level Storage

- **Embedded storage layer for apps/CLIs**
  - Use as the persistence layer for apps that manage structured files (wikis, note systems, CAD project stores, etc.).
  - The app stores states as trees by hash; a separate index maps human identifiers → content hashes.

- **Undo/redo and timelines**
  - Track every state of a project/config as a root hash.
  - Implement time-travel, undo, and diffs by comparing trees.

- **“Packages” of content-addressed bundles**
  - Ship self-contained bundles of config/scripts/resources as a single tree hash.
  - Consumers verify integrity by recomputing the hash.

### Research, Experimentation & Reproducibility

- **Reproducible experiments**
  - Store code, params, and data snapshots all by hash; record an “experiment” as a tuple of hashes.
  - You can fully reconstruct what was run without caring where files used to live.

- **Deduped scratch space for notebooks**
  - Notebooks / scripts can store intermediate results as hashed blobs, reusing them across runs and branches.

### System & Infra Use Cases

- **Config store for local tooling**
  - Tools that need robust configuration history can store each config snapshot as a tree.
  - Rollback just means changing a ref to an older hash.

- **Base for a custom VCS**
  - Use it as the low-level object store; build commits/branches/tags on top.
  - You avoid re-implementing blob/tree plumbing.

- **Mini container / rootfs registry (local)**
  - Store filesystem roots (e.g., chroot trees, sandbox images) by hash.
  - Very fast cloning by reusing shared blobs; just point multiple “instances” to the same tree.

### Testing, Security & Integrity

- **Golden-test fixtures by hash**
  - Store test fixtures and expected outputs addressed by content.
  - Makes it trivial to verify that generated outputs exactly match golden versions.

- **Integrity and tamper detection**
  - Use the store as a canonical representation of “trusted” content.
  - Re-hash live directories and compare to stored tree hashes to detect corruption or unauthorized changes.

- **Reproducible builds verification**
  - Given a tree hash for "expected output," compare the result of a build to that tree.
  - Simple yes/no reproducibility check without a complex protocol.

## Installation

```bash
# Build from source
cargo build --release -p casq

# Install to your system
cargo install --path ./casq

# Or copy the binary
cp target/release/casq ~/.local/bin/
```

## Project Structure

This is a Rust workspace with two crates:

- **`casq_core/`** - Core library implementing the storage engine with compression and chunking (92 unit tests)
- **`casq/`** - CLI binary providing the user interface

**Test Coverage:**
- 121 Rust unit tests (100% pass rate)
- 23 property tests (generative invariant verification)
- 313 Python integration tests (including 26 JSON output tests, 19 orphan tests)
- Comprehensive coverage of compression, chunking, JSON output, orphan discovery, and all core features

## Documentation

- **[CLI README](casq/README.md)** - Complete command reference and examples
- **[Core Library README](casq_core/README.md)** - API documentation and architecture
- **[NOTES.md](NOTES.md)** - Design specification and implementation details

## Performance & Storage Efficiency

**Performance:**
- BLAKE3 hashing (fast, cryptographically secure)
- Transparent zstd compression (~500 MB/s, level 3)
- FastCDC chunking for incremental backups (~1 GB/s processing)
- Streaming I/O for large files (no full buffering)
- Automatic deduplication via content addressing (including chunk-level deduplication)
- Directory sharding to prevent filesystem bottlenecks

**Storage Efficiency:**
- **Compression**: 3-5x reduction for text files, 2-3x for mixed data
- **Chunking**: Change 1 byte in 1GB file → store only ~512KB (changed chunk)
- **Deduplication**: Shared content across files stored only once
- **Example**: 10 files with identical 5MB section = 5MB stored (not 50MB)

**Design Limitations (By Choice):**
- Local-only (no network/remote storage)
- Single-user (no concurrent access)
- No encryption at rest (planned for future)
- No parallel operations (single-threaded)
- POSIX-only for full permission preservation

## License

> [Apache-2.0](LICENSE)
