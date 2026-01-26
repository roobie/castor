# `casq`

![casq logo](assets/logo.jpeg)

**A content-addressed file store with compression and chunking.**

This is Alpha level software.

`casq` is a single-binary tool for storing files and directories by their cryptographic hash. Think of it as a lightweight git object store or restic backend—but simpler, local-only, and purpose-built for content-addressed storage with modern efficiency features.

**Why `casq`?**
- **Automatic deduplication** - Identical content stored only once, even across different directories
- **Transparent compression** - 3-5x storage reduction with zstd (files ≥ 4KB automatically compressed)
- **Content-defined chunking** - Incremental backups with FastCDC v2020 (files ≥ 1MB split into variable chunks, 60-80% reuse after edits)
- **Content addressing** - Files identified by cryptographic hash, not by path
- **Stdin support** - Pipe data directly from commands (e.g., `curl | casq put -`)
- **Garbage collection** - Reclaim space from unreferenced objects with mark & sweep
- **Simple & fast** - No databases, no network, just files on disk with BLAKE3 hashing
- **Embeddable** - Rust library (`casq_core`) + CLI binary, easily integrated into your tools

