# `casq`

**A minimal content-addressed file store using BLAKE3.**

Castor is a single-binary tool for storing files and directories by their cryptographic hash. Think of it as a lightweight git object store or restic backend—but simpler, local-only, and purpose-built for content-addressed storage without the version control overhead.

**Why Castor?**
- **Automatic deduplication** - Identical content stored only once, even across different directories
- **Content addressing** - Files identified by cryptographic hash, not by path
- **Garbage collection** - Reclaim space from unreferenced objects with mark & sweep
- **Simple & fast** - No databases, no network, just files on disk with BLAKE3 hashing
- **Embeddable** - Rust library (`casq_core`) + CLI binary, easily integrated into your tools

## Quick Start

```bash
# Initialize a store
casq init

# Add files and directories (automatically deduplicated)
casq add myproject/ --ref-name snapshot-2024-01-21

# List what you have
casq ls
# Output: snapshot-2024-01-21 -> abc123...

# Explore a tree
casq ls abc123...

# Retrieve content
casq cat <hash>                    # Stream a file to stdout
casq materialize abc123... ./out   # Restore entire directory

# Clean up unreferenced objects
casq gc --dry-run                  # Preview
casq gc                            # Actually delete
```

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

- **`casq_core/`** - Core library implementing the storage engine (68 unit tests)
- **`casq/`** - CLI binary providing the user interface

## Documentation

- **[CLI README](casq/README.md)** - Complete command reference and examples
- **[Core Library README](casq_core/README.md)** - API documentation and architecture
- **[NOTES.md](NOTES.md)** - Design specification and implementation details

## Performance & Limitations

**Performance:**
- BLAKE3 hashing (fast, cryptographically secure)
- Streaming I/O for large files (no full buffering)
- Automatic deduplication via content addressing
- Directory sharding to prevent filesystem bottlenecks

**Current Limitations (MVP scope):**
- Local-only (no network/remote storage)
- Single-user (no concurrent access)
- No compression or encryption
- No chunking (each file = one blob)
- POSIX-only for full permission preservation

## License

See [LICENSE](LICENSE) file for details.
