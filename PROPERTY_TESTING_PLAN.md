# Property Testing Implementation Plan for casq

## Phase 1: Property-Based Testing (Immediate Focus)

### Context

casq v0.4.0 is production-ready with 92 unit tests and 248+ integration tests. To achieve production-grade robustness, we need property-based testing to systematically verify critical invariants across wide input ranges.

**Goal:** Add 23 property tests using proptest to verify core invariants.

---

## Framework: proptest

**Choice:** `proptest = "1.4"` (dev-dependency)

**Rationale:**
- Industry standard in Rust ecosystem
- Excellent shrinking to minimal failing cases
- Good ergonomics with `proptest!` macro
- Configurable test case counts (256 for CI, 1000+ local)
- Integrates seamlessly with `cargo test`

---

## Critical Invariants (23 Properties)

### Hash Module (5 properties) - `hash.rs`

1. **Hash determinism:** `∀ data. hash(data) == hash(data)`
2. **Hex encoding bijection:** `∀ hash. from_hex(to_hex(hash)) == hash`
3. **Prefix + suffix = full hex:** `prefix + suffix == to_hex(hash)`
4. **Invalid hex length fails:** Wrong length → Error
5. **Algorithm conversions bijective:** `from_id(to_id(algo)) == algo`

### Object Module (4 properties) - `object.rs`

6. **Header round-trip:** `decode(encode(header)) == header`
7. **ChunkList round-trip:** `decode(encode(chunks)) == chunks`
8. **Invalid chunk sizes rejected:** `len % 40 != 0 => Error`
9. **ObjectType conversions:** `from_u8(to_u8(type)) == type`

### Tree Module (5 properties) - `tree.rs`

10. **TreeEntry round-trip:** `decode(encode(entry)) == entry`
11. **Tree canonicalization:** Shuffle entries → same hash after sorting
12. **Empty names rejected:** `name.is_empty() => Error`
13. **Null bytes rejected:** `name.contains('\0') => Error`
14. **Long names rejected:** `name.len() > 255 => Error`

### Chunking Module (3 properties) - `chunking.rs`

15. **Chunk sizes bounded:** `min <= chunk_size <= max`
16. **Chunking deterministic:** Same data → identical chunks
17. **Total size preserved:** `sum(chunk_sizes) == data.len()`

### Compression (2 properties) - `store.rs`

18. **Compression identity:** `decompress(compress(data)) == data`
19. **Threshold respected:** `size < 4KB => not compressed`

### GC and Refs (4 properties) - `gc.rs`, `refs.rs`

20. **GC preserves referenced:** Never deletes reachable objects
21. **GC deletes unreferenced:** Deletes unreachable objects
22. **GC idempotent:** Running twice → same result
23. **Valid ref names:** Reasonable names accepted

---

## Implementation Strategy

### File Organization

Property tests are **inline** in existing test modules:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // Existing unit tests first...

    // Property tests after unit tests
    proptest! {
        #![proptest_config(ProptestConfig {
            cases: 256,  // CI-friendly
            max_shrink_iters: 10000,
            ..ProptestConfig::default()
        })]

        #[test]
        fn prop_invariant_name(input in strategy) {
            // test the invariant
        }
    }
}
```

**Rationale:**
- Fast iteration with `cargo test`
- Close to implementation
- Share fixtures with unit tests

---

## Implementation Examples

### Example 1: Hash Module (`hash.rs`)

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // Existing unit tests...

    proptest! {
        #![proptest_config(ProptestConfig {
            cases: 256,
            max_shrink_iters: 10000,
            ..ProptestConfig::default()
        })]

        /// Property 1: Hash determinism
        #[test]
        fn prop_hash_deterministic(data: Vec<u8>) {
            let hash1 = Hash::hash_bytes(&data);
            let hash2 = Hash::hash_bytes(&data);
            prop_assert_eq!(hash1, hash2);
        }

        /// Property 2: Hex encoding bijection
        #[test]
        fn prop_hex_roundtrip(bytes in prop::array::uniform32(any::<u8>())) {
            let hash = Hash::from_bytes(bytes);
            let hex = hash.to_hex();
            let parsed = Hash::from_hex(&hex)?;
            prop_assert_eq!(hash, parsed);
        }

        /// Property 3: Prefix + suffix reconstruction
        #[test]
        fn prop_prefix_suffix_concat(bytes in prop::array::uniform32(any::<u8>())) {
            let hash = Hash::from_bytes(bytes);
            let full = hash.to_hex();
            let reconstructed = format!("{}{}", hash.prefix(), hash.suffix());
            prop_assert_eq!(full, reconstructed);
        }

        /// Property 4: Invalid hex length always fails
        #[test]
        fn prop_invalid_hex_length_fails(
            s in "[0-9a-f]{0,63}|[0-9a-f]{65,128}"
        ) {
            prop_assert!(Hash::from_hex(&s).is_err());
        }

        /// Property 5: Algorithm conversions
        #[test]
        fn prop_algorithm_roundtrip(
            algo in prop::sample::select(vec![Algorithm::Blake3])
        ) {
            let s = algo.as_str();
            let id = algo.id();
            prop_assert_eq!(Algorithm::parse(s)?, algo);
            prop_assert_eq!(Algorithm::from_id(id)?, algo);
        }
    }
}
```

### Example 2: Tree Canonicalization (`tree.rs`)

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    // Strategy for valid entry names (1-255 chars, no nulls)
    fn arb_entry_name() -> impl Strategy<Value = String> {
        "[a-zA-Z0-9._-]{1,255}"
            .prop_filter("no null bytes", |s| !s.contains('\0'))
    }

    fn arb_tree_entry() -> impl Strategy<Value = TreeEntry> {
        (
            prop::sample::select(vec![EntryType::Blob, EntryType::Tree]),
            any::<u32>(),
            prop::array::uniform32(any::<u8>()),
            arb_entry_name(),
        ).prop_map(|(entry_type, mode, hash_bytes, name)| {
            TreeEntry::new(
                entry_type,
                mode,
                Hash::from_bytes(hash_bytes),
                name,
            ).unwrap()
        })
    }

    proptest! {
        /// Property 10: TreeEntry round-trip
        #[test]
        fn prop_tree_entry_roundtrip(entry in arb_tree_entry()) {
            let encoded = entry.encode();
            let decoded = TreeEntry::decode(&mut &encoded[..])?;
            prop_assert_eq!(entry, decoded);
        }

        /// Property 11: Tree canonicalization order-independent
        #[test]
        fn prop_tree_canonicalization(
            entries in prop::collection::vec(arb_tree_entry(), 1..20)
        ) {
            // Hash of sorted entries
            let mut sorted1 = entries.clone();
            sorted1.sort_by(|a, b| a.name.cmp(&b.name));
            let encoded1 = encode_tree_entries(&sorted1);
            let hash1 = Hash::hash_bytes(&encoded1);

            // Hash after shuffling and re-sorting
            let mut shuffled = entries;
            shuffled.reverse();
            shuffled.sort_by(|a, b| a.name.cmp(&b.name));
            let encoded2 = encode_tree_entries(&shuffled);
            let hash2 = Hash::hash_bytes(&encoded2);

            prop_assert_eq!(hash1, hash2,
                "Tree hash must be independent of input ordering");
        }

        /// Property 12: Empty names rejected
        #[test]
        fn prop_empty_name_rejected(
            entry_type in prop::sample::select(vec![EntryType::Blob, EntryType::Tree]),
            mode in any::<u32>(),
            hash_bytes in prop::array::uniform32(any::<u8>()),
        ) {
            let result = TreeEntry::new(
                entry_type,
                mode,
                Hash::from_bytes(hash_bytes),
                String::new(),
            );
            prop_assert!(result.is_err());
        }

        /// Property 13: Names with null bytes rejected
        #[test]
        fn prop_null_byte_rejected(
            prefix in "[a-zA-Z0-9]{0,10}",
            suffix in "[a-zA-Z0-9]{0,10}",
        ) {
            let name = format!("{}\0{}", prefix, suffix);
            let result = TreeEntry::new(
                EntryType::Blob,
                0o644,
                Hash::hash_bytes(b"test"),
                name,
            );
            prop_assert!(result.is_err());
        }

        /// Property 14: Names >255 bytes rejected
        #[test]
        fn prop_long_name_rejected(name in "[a-zA-Z]{256,300}") {
            let result = TreeEntry::new(
                EntryType::Blob,
                0o644,
                Hash::hash_bytes(b"test"),
                name,
            );
            prop_assert!(result.is_err());
        }
    }
}

fn encode_tree_entries(entries: &[TreeEntry]) -> Vec<u8> {
    let mut buf = Vec::new();
    for entry in entries {
        buf.extend_from_slice(&entry.encode());
    }
    buf
}
```

### Example 3: GC Properties (`gc.rs`)

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;
    use tempfile::TempDir;

    // Test harness for GC properties
    struct TestStoreSetup {
        _temp_dir: TempDir,
        store: Store,
        referenced_hash: Hash,
        unreferenced_hash: Hash,
    }

    impl TestStoreSetup {
        fn new() -> Result<Self> {
            let temp_dir = TempDir::new()?;
            let mut store = Store::init(temp_dir.path(), Algorithm::Blake3)?;

            // Create referenced blob
            let ref_data = b"referenced content";
            let referenced_hash = store.put_blob(&mut &ref_data[..])?;
            store.refs().add("test-ref", &referenced_hash)?;

            // Create unreferenced blob
            let unref_data = b"unreferenced content";
            let unreferenced_hash = store.put_blob(&mut &unref_data[..])?;

            Ok(TestStoreSetup {
                _temp_dir: temp_dir,
                store,
                referenced_hash,
                unreferenced_hash,
            })
        }
    }

    proptest! {
        #![proptest_config(ProptestConfig {
            cases: 32,  // Expensive tests, fewer cases
            ..ProptestConfig::default()
        })]

        /// Property 20: GC preserves referenced objects
        #[test]
        fn prop_gc_preserves_referenced(_seed in any::<u64>()) {
            let setup = TestStoreSetup::new().unwrap();
            let stats = setup.store.gc(false).unwrap();

            // Referenced object must still exist
            prop_assert!(
                setup.store.get_blob(&setup.referenced_hash).is_ok(),
                "GC deleted a referenced object"
            );

            // Should have deleted at least one object
            prop_assert!(
                stats.objects_deleted > 0,
                "GC should delete unreferenced objects"
            );
        }

        /// Property 21: GC deletes unreferenced objects
        #[test]
        fn prop_gc_deletes_unreferenced(_seed in any::<u64>()) {
            let setup = TestStoreSetup::new().unwrap();
            setup.store.gc(false).unwrap();

            // Unreferenced object must be deleted
            prop_assert!(
                setup.store.get_blob(&setup.unreferenced_hash).is_err(),
                "GC failed to delete unreferenced object"
            );
        }

        /// Property 22: GC is idempotent
        #[test]
        fn prop_gc_idempotent(_seed in any::<u64>()) {
            let setup = TestStoreSetup::new().unwrap();

            let stats1 = setup.store.gc(false).unwrap();
            let stats2 = setup.store.gc(false).unwrap();

            prop_assert_eq!(
                stats2.objects_deleted, 0,
                "GC is not idempotent - deleted objects on second run"
            );
        }
    }
}
```

**Note:** GC properties use actual filesystem stores, so they're slower. Use reduced case counts (32 vs 256).

---

## Implementation Plan

### Phase 1: Core Modules (Week 1)

**Files to modify:**

1. **`/workspace/casq_core/Cargo.toml`**
   ```toml
   [dev-dependencies]
   proptest = "1.4"  # Add this line
   ```

2. **`/workspace/casq_core/src/hash.rs`** (~50 lines)
   - Add Properties 1-5
   - Straightforward with `any::<Vec<u8>>()`

3. **`/workspace/casq_core/src/object.rs`** (~100 lines)
   - Add Properties 6-9
   - Custom strategies for ObjectHeader

4. **`/workspace/.github/workflows/rust.yml`** (update)
   ```yaml
   - name: Run property tests
     run: |
       echo "Running property tests..."
       cargo test --lib proptest
       echo "Property tests completed"
   ```

### Phase 2: Trees and Chunking (Week 2)

**Files to modify:**

5. **`/workspace/casq_core/src/tree.rs`** (~120 lines)
   - Add Properties 10-14
   - Complex: custom strategies for valid/invalid names

6. **`/workspace/casq_core/src/chunking.rs`** (~60 lines)
   - Add Properties 15-17
   - Test chunk size constraints and determinism

7. **`/workspace/casq_core/src/store.rs`** (~40 lines)
   - Add Properties 18-19
   - Compression round-trip and threshold

### Phase 3: GC and Documentation (Week 3)

**Files to modify:**

8. **`/workspace/casq_core/src/gc.rs`** (~80 lines)
   - Add Properties 20-22
   - Requires test harness with temp stores

9. **`/workspace/casq_core/src/refs.rs`** (~20 lines)
   - Add Property 23
   - Validate ref name acceptance

10. **`/workspace/TESTING.md`** (update)
    - Add property testing section

11. **`/workspace/README.md`** (update)
    - Update test statistics: "23 property tests"

12. **`/workspace/CLAUDE.md`** (update)
    - Add property testing guidelines

---

## Running Property Tests

### Local Development

```bash
# All tests (including properties)
cargo test

# Only property tests
cargo test proptest

# Specific module
cargo test -p casq_core hash::tests::prop

# With verbose output
cargo test proptest -- --nocapture

# More thorough (1000 cases)
PROPTEST_CASES=1000 cargo test proptest
```

### CI Integration

Property tests run on every commit with 256 cases:
- Expected runtime: +5-10 seconds
- Runs after unit tests, before integration tests

---

## Performance Considerations

### Test Speed Optimization

1. **Use small input ranges** where possible
2. **Reduce cases for expensive tests:**
   - Hash/Object/Tree: 256 cases (fast)
   - Chunking: 128 cases (medium)
   - GC: 32 cases (slow, creates temp stores)
3. **Profile slow tests:**
   ```bash
   cargo test --release proptest -- --nocapture
   ```
4. **Mark very slow tests:**
   ```rust
   #[test]
   #[ignore]
   fn prop_very_expensive_test() { /* ... */ }
   ```

### Expected Runtimes

- Hash properties (5): ~2 seconds
- Object properties (4): ~3 seconds
- Tree properties (5): ~5 seconds
- Chunking properties (3): ~4 seconds
- Compression properties (2): ~3 seconds
- GC properties (3): ~8 seconds
- Ref properties (1): ~1 second

**Total:** ~26 seconds for full property test suite

---

## Success Criteria

After implementation:

✅ All 23 properties pass consistently
✅ CI runtime increase < 15 seconds
✅ No flaky tests (properties should be deterministic or use seeds)
✅ Documentation updated
✅ Test coverage > 90% on critical modules

---

## Maintenance Guidelines

### Writing New Property Tests

1. **Name with `prop_` prefix** for easy filtering
2. **Document the invariant** being tested
3. **Use appropriate case counts:**
   - 256 for CI (default)
   - 64-128 for expensive tests
   - 1000+ for thorough local testing
4. **Don't duplicate unit tests** - test invariants, not specific cases
5. **Keep tests fast** - profile and optimize

### Reviewing Property Test Failures

When a property test fails:

1. **Don't immediately "fix" the test** - it may have found a real bug
2. **Examine the minimal failing case** from shrinking
3. **Reproduce with a unit test** to debug
4. **Fix the production code** if it's a bug
5. **Fix the property** if it's a false positive
6. **Document the fix** and add regression test

---

## Next Steps

After property testing is implemented:

1. **Monitor CI performance** - ensure < 30 sec total
2. **Track coverage improvements** - measure impact
3. **Consider fuzzing** - See FUZZING_PLAN.md (future QA)
4. **Expand to new modules** as features are added
5. **Share lessons learned** in documentation

---

## Summary

**Scope:** 23 property tests across 6 modules
**Timeline:** 3 weeks phased implementation
**Impact:**
- Systematic verification of critical invariants
- Regression prevention through generative testing
- Executable specifications for core behaviors
- Production-grade robustness

**Risk:** Low - additive testing, no production code changes

This plan focuses on property testing as Phase 1, establishing a solid foundation for code quality before advancing to fuzzing and other QA techniques.
