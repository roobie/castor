# Fuzzing Implementation Plan for casq

## Future Quality Assurance: Fuzzing Strategy

**Status:** Future work - implement after property testing is complete

**Purpose:** Harden binary parsers against malformed/malicious input through coverage-guided fuzzing

---

## Overview

After completing property testing (see PROPERTY_TESTING_PLAN.md), implement fuzzing to find edge cases in binary parsing code that property tests might miss.

**Goal:** Add 7 fuzz targets using cargo-fuzz for comprehensive parser robustness

---

## Framework: cargo-fuzz

**Choice:** `cargo-fuzz` with libFuzzer backend

**Rationale:**
- Standard Rust fuzzing tool
- Coverage-guided mutation
- Built-in corpus management
- Easy CI integration
- Works with `arbitrary` crate

---

## Fuzz Targets (7 targets)

### Priority 1: Binary Parsers (Critical Security)

1. **object_header_decode**
   - Target: `ObjectHeader::decode(object.rs:173)`
   - Input: 16-byte binary
   - Invariant: Never panic, only return Err

2. **chunk_list_decode**
   - Target: `ChunkList::decode(object.rs:278)`
   - Input: Variable binary (multiples of 40)
   - Invariant: Reject non-multiples gracefully

3. **tree_entry_decode**
   - Target: `TreeEntry::decode(tree.rs:121)`
   - Input: Variable binary
   - Invariant: Handle truncation, invalid UTF-8

### Priority 2: Text Parsers

4. **journal_from_line**
   - Target: `JournalEntry::from_line(journal.rs:52)`
   - Input: Pipe-delimited text (5 fields)

5. **hash_from_hex**
   - Target: `Hash::from_hex(hash.rs:61)`
   - Input: Hex string

6. **store_parse_config**
   - Target: `Store::parse_config(store.rs:111)`
   - Input: Key=value lines

### Priority 3: Compression

7. **compression_roundtrip**
   - Target: Compression/decompression in store.rs
   - Input: Arbitrary data + compression type

---

## Directory Structure

```
/workspace/
├── fuzz/                       # NEW: Fuzz crate
│   ├── Cargo.toml             # Fuzz manifest
│   ├── fuzz_targets/          # Individual targets
│   │   ├── object_header_decode.rs
│   │   ├── chunk_list_decode.rs
│   │   ├── tree_entry_decode.rs
│   │   ├── journal_from_line.rs
│   │   ├── hash_from_hex.rs
│   │   ├── store_parse_config.rs
│   │   └── compression_roundtrip.rs
│   ├── corpus/                # Seed inputs (git-ignored)
│   └── dictionaries/          # Dictionary files for text fuzzing
│       ├── hex.dict
│       └── journal.dict
```

---

## Example Fuzz Target

**File: `/workspace/fuzz/fuzz_targets/object_header_decode.rs`**

```rust
#![no_main]

use libfuzzer_sys::fuzz_target;
use casq_core::object::ObjectHeader;

fuzz_target!(|data: &[u8]| {
    // Should never panic on any input
    // May return Err for invalid headers, but must not crash
    let _ = ObjectHeader::decode(data);
});
```

**Run:**
```bash
cargo fuzz run object_header_decode -- -max_total_time=300
```

---

## Implementation Steps

1. **Setup fuzz crate:**
   ```bash
   cargo install cargo-fuzz
   cargo fuzz init
   ```

2. **Create fuzz/Cargo.toml:**
   ```toml
   [package]
   name = "casq-fuzz"
   version = "0.0.0"
   publish = false
   edition = "2024"

   [package.metadata]
   cargo-fuzz = true

   [dependencies]
   libfuzzer-sys = "0.4"
   casq_core = { path = "../casq_core" }
   arbitrary = { version = "1.3", features = ["derive"] }

   [workspace]
   ```

3. **Implement each target** (see examples above)

4. **Create seed corpus** for each target

5. **Add CI workflow** for nightly fuzzing

6. **Run initial campaign** (1 hour per target)

---

## CI Integration (Nightly)

**File: `/workspace/.github/workflows/fuzz.yml`**

```yaml
name: Fuzzing

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
  workflow_dispatch:

jobs:
  fuzz:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        target: [object_header_decode, chunk_list_decode, tree_entry_decode,
                 journal_from_line, hash_from_hex, compression_roundtrip]

    steps:
    - uses: actions/checkout@v4

    - name: Install cargo-fuzz
      run: cargo install cargo-fuzz

    - name: Restore corpus
      uses: actions/cache@v3
      with:
        path: fuzz/corpus
        key: fuzz-corpus-${{ matrix.target }}-${{ github.sha }}
        restore-keys: fuzz-corpus-${{ matrix.target }}-

    - name: Run fuzzer (5 minutes)
      run: |
        cd fuzz
        timeout 300 cargo fuzz run ${{ matrix.target }} || true

    - name: Check for crashes
      run: |
        if [ -d "fuzz/artifacts/${{ matrix.target }}" ] && [ "$(ls -A fuzz/artifacts/${{ matrix.target }})" ]; then
          echo "::error::Crashes found in ${{ matrix.target }}"
          exit 1
        fi

    - name: Upload crashes
      if: failure()
      uses: actions/upload-artifact@v3
      with:
        name: fuzz-artifacts-${{ matrix.target }}
        path: fuzz/artifacts/${{ matrix.target }}/
```

---

## Bug Triage Workflow

When fuzzing finds a crash:

1. **Capture:** `ls fuzz/artifacts/object_header_decode/`
2. **Reproduce:** `cargo fuzz run object_header_decode artifacts/crash-xyz`
3. **Minimize:** `cargo fuzz tmin object_header_decode artifacts/crash-xyz`
4. **Analyze:** Create unit test from crash
5. **Fix:** Add bounds checking or validation
6. **Verify:** Re-run fuzzer with crash input
7. **Regression test:** Add to corpus

---

## Advanced Techniques

### Dictionary Files

For text-based targets, provide dictionaries:

**File: `/workspace/fuzz/dictionaries/hex.dict`**

```
"0123456789abcdef"
"0000000000000000000000000000000000000000000000000000000000000000"
"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
""
"g"  # Invalid
"000"  # Wrong length
```

### Corpus Seeding

Create valid seed inputs for faster coverage:

```rust
// Helper script to generate seeds
let header = ObjectHeader::new(ObjectType::Blob, Algorithm::Blake3, CompressionType::None, 1024);
std::fs::write("fuzz/corpus/object_header_decode/valid_blob", header.encode()).unwrap();
```

---

## Expected Outcomes

**Likely findings:**
- Edge cases in binary parsing (off-by-one, overflows)
- UTF-8 handling issues
- Compression edge cases
- Chunking boundary issues

**Historical precedent:** 30-40% of fuzz targets find panics

---

## Commands

```bash
# Install
cargo install cargo-fuzz

# List targets
cargo fuzz list

# Run target (Ctrl+C to stop)
cargo fuzz run object_header_decode

# Run for 5 minutes
cargo fuzz run object_header_decode -- -max_total_time=300

# With dictionary
cargo fuzz run hash_from_hex -- -dict=fuzz/dictionaries/hex.dict

# View coverage
cargo fuzz coverage object_header_decode
```

---

## Success Criteria

✅ Zero crashes after 4+ hours per target
✅ Nightly CI integration successful
✅ Corpus preserved for regression detection
✅ Coverage > 90% on parser modules

---

## Timeline

**After property testing is complete:**
- Week 1: Setup + Priority 1 targets (binary parsers)
- Week 2: Priority 2 + 3 targets (text + compression)
- Week 3: CI integration + documentation

**Total:** ~3 weeks after property testing

---

## Summary

Fuzzing complements property testing by:
- Finding deep edge cases in parsers
- Testing with truly arbitrary input
- Providing continuous regression detection
- Hardening against malicious input

**Status:** Future work - defer until property testing complete

See PROPERTY_TESTING_PLAN.md for Phase 1 (immediate focus).
