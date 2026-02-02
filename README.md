# `casq`

![casq logo](assets/logo.jpeg)
[![License](https://img.shields.io/github/license/roobie/casq?style=for-the-badge)](LICENSE)
[![Release](https://img.shields.io/github/v/release/roobie/casq?style=for-the-badge)](https://github.com/roobie/casq/releases)

**A local content-addressed file store with compression and chunking.**

This is **Alpha** level software.

`casq` is a single-binary tool for storing files and directories by their cryptographic hash. Think of it as a lightweight git object store or restic backend—but simpler, local-only, and purpose-built for content-addressed storage with modern efficiency features.

**Why `casq`?**
- **Automatic deduplication** - Identical content stored only once, even across different directories
- **Content-defined chunking** - Incremental backups with FastCDC v2020 (files ≥ 1MB split into variable chunks, 60-80% reuse after edits)
- **Transparent compression** - 3-5x storage reduction with zstd (files ≥ 4KB automatically compressed)
- **Content addressing** - Files identified by cryptographic hash, not by path (however, custom references are supported)
- **Garbage collection** - Reclaim space from unreferenced objects with mark & sweep
- **Simple & fast** - No databases, no network, just files on disk with BLAKE3 hashing
- **Embeddable** - Rust library (`casq_core`) + CLI binary, easily integrated into your tools

## Representative CLI example

```bash
# Use an environment variable to set the root. It is also possible to use --root/-R per invocation. Defaults to current working directory.
export CASQ_ROOT="/var/my-casq"

# Initialize the casq root - echoes the full path to the root directory.
casq initialize #>/var/my-casq
# Put a file system tree into the casq with a custom reference - echoes the hash
casq put /some/tree --reference tree@1 #>d856ec8e03cce04358fbd6a5135823574dea4de9ae6a6f511e3c060f33d144d4

# Put a blob into the casq with a custom reference via piping - echoes the hash
casq put --reference "big-blob@$(date -I)" - < curl https://big-blob.wherever #>d856ec8e03cce04358fbd6a5135823574dea4de9ae6a6f511e3c060f33d144d4
# Put a blob into the casq with a custom reference via piping - echoes the hash
curl https://example.org | casq put --reference "example.org@$(date +%s)" - #>454499efc25b742a1eaa37e1b2ec934638b05cef87b036235c087d54ee5dde59

# Get metadata about an object:
casq metadata tree@1 --json #>
#{
#  "success": true,
#  "result_code": 0,
#  "type": "Tree",
#  "hash": "d856ec8e03cce04358fbd6a5135823574dea4de9ae6a6f511e3c060f33d144d4",
#  "entry_count": 1,
#  "path": "./casq-store/objects/blake3-256/d8/56ec8e03cce04358fbd6a5135823574dea4de9ae6a6f511e3c060f33d144d4"
#}

# List the children of tree
casq list tree@1 #>file1\nfile2 etc
casq list --long tree@1 #>(listing of tree's children with most metadata)

# Read a blob and pipe it through less
casq get be616640346d71f639f55014a17229a8e6ab7d164b44a702d1c04da0d4bd48e3 | less

# List all references
casq references list
# Add a reference; key => value: casq references add REFERENCE HASH
casq references add my-custom-ref be616640346d71f639f55014a17229a8e6ab7d164b44a702d1c04da0d4bd48e3
# So now we can `get` it by ref
casq get my-custom-ref | less
# Remove the reference: casq references remove REFERENCE
casq references remove my-custom-ref

# Shows all objects that are unreferenced
casq find-orphans #>...

# Show all unreferenced data that would be deleted
casq collect-garbage --dry-run
# Deletes all unreferenced data
casq collect-garbage
```

So, general usage pattern:
1. `initialize`
2. `put` (with --reference)
3. read: `metadata`, `get`, `list`
4. manage references: `references add/list/remove` and `find-orphans`
5. `collect-garbage`

Development

Run test coverage for the core crate with the mise task (requires cargo-tarpaulin):

```bash
# Generate HTML + XML coverage reports for casq_core
mise run coverage_core
# Reports are written to target/coverage/casq_core/
```

## License

Free, and open-source

> Apache-2.0
