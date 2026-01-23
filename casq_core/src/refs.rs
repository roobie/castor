//! Reference management for named GC roots.

use crate::error::{Error, Result};
use crate::hash::Hash;
use crate::store::Store;
use std::fs;
use std::path::PathBuf;

/// Manages named references (GC roots) in the store.
pub struct RefManager<'a> {
    store: &'a Store,
}

impl<'a> RefManager<'a> {
    /// Create a new RefManager for the given store.
    pub(crate) fn new(store: &'a Store) -> Self {
        Self { store }
    }

    /// Get the path to a reference file.
    fn ref_path(&self, name: &str) -> Result<PathBuf> {
        // Validate name - no path traversal
        if name.contains("..") || name.contains('/') || name.contains('\\') {
            return Err(Error::invalid_ref(format!(
                "Invalid ref name: {} (must not contain .. or path separators)",
                name
            )));
        }

        if name.is_empty() {
            return Err(Error::invalid_ref("Ref name cannot be empty"));
        }

        Ok(self.store.root().join("refs").join(name))
    }

    /// Add or update a reference.
    ///
    /// Appends the hash to the ref file (one hash per line).
    /// The last non-empty line is the current value.
    pub fn add(&self, name: &str, hash: &Hash) -> Result<()> {
        let path = self.ref_path(name)?;
        let hash_str = format!("{}\n", hash.to_hex());

        // Append to file
        let mut file = fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)?;

        use std::io::Write;
        file.write_all(hash_str.as_bytes())?;

        Ok(())
    }

    /// Get the current value of a reference.
    ///
    /// Returns the last non-empty, non-comment line.
    pub fn get(&self, name: &str) -> Result<Option<Hash>> {
        let path = self.ref_path(name)?;

        if !path.exists() {
            return Ok(None);
        }

        let content = fs::read_to_string(&path)?;
        let mut last_hash = None;

        for line in content.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with('#') {
                continue;
            }

            // Try to parse as hash
            match Hash::from_hex(line) {
                Ok(hash) => last_hash = Some(hash),
                Err(_) => continue, // Ignore invalid lines
            }
        }

        Ok(last_hash)
    }

    /// List all references.
    ///
    /// Returns a vector of (name, hash) pairs.
    pub fn list(&self) -> Result<Vec<(String, Hash)>> {
        let refs_dir = self.store.root().join("refs");
        let mut refs = Vec::new();

        if !refs_dir.exists() {
            return Ok(refs);
        }

        for entry in fs::read_dir(&refs_dir)? {
            let entry = entry?;
            let path = entry.path();

            if path.is_file()
                && let Some(name) = path.file_name().and_then(|n| n.to_str())
                && let Some(hash) = self.get(name)?
            {
                refs.push((name.to_string(), hash));
            }
        }

        refs.sort_by(|a, b| a.0.cmp(&b.0));
        Ok(refs)
    }

    /// Remove a reference.
    pub fn remove(&self, name: &str) -> Result<()> {
        let path = self.ref_path(name)?;

        if !path.exists() {
            return Err(Error::ref_not_found(name));
        }

        fs::remove_file(&path)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hash::Algorithm;
    use tempfile::TempDir;

    #[test]
    fn test_ref_add_and_get() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();
        let refs = store.refs();

        let hash = Hash::hash_bytes(b"test");
        refs.add("myref", &hash).unwrap();

        let retrieved = refs.get("myref").unwrap();
        assert_eq!(retrieved, Some(hash));
    }

    #[test]
    fn test_ref_get_nonexistent() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();
        let refs = store.refs();

        let retrieved = refs.get("nonexistent").unwrap();
        assert_eq!(retrieved, None);
    }

    #[test]
    fn test_ref_update() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();
        let refs = store.refs();

        let hash1 = Hash::hash_bytes(b"test1");
        let hash2 = Hash::hash_bytes(b"test2");

        refs.add("myref", &hash1).unwrap();
        refs.add("myref", &hash2).unwrap();

        // Should get the last one
        let retrieved = refs.get("myref").unwrap();
        assert_eq!(retrieved, Some(hash2));
    }

    #[test]
    fn test_ref_list() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();
        let refs = store.refs();

        let hash1 = Hash::hash_bytes(b"test1");
        let hash2 = Hash::hash_bytes(b"test2");

        refs.add("ref1", &hash1).unwrap();
        refs.add("ref2", &hash2).unwrap();

        let list = refs.list().unwrap();
        assert_eq!(list.len(), 2);
        assert_eq!(list[0].0, "ref1");
        assert_eq!(list[0].1, hash1);
        assert_eq!(list[1].0, "ref2");
        assert_eq!(list[1].1, hash2);
    }

    #[test]
    fn test_ref_remove() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();
        let refs = store.refs();

        let hash = Hash::hash_bytes(b"test");
        refs.add("myref", &hash).unwrap();

        refs.remove("myref").unwrap();

        let retrieved = refs.get("myref").unwrap();
        assert_eq!(retrieved, None);
    }

    #[test]
    fn test_ref_invalid_name() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();
        let refs = store.refs();

        let hash = Hash::hash_bytes(b"test");

        assert!(refs.add("../etc/passwd", &hash).is_err());
        assert!(refs.add("foo/bar", &hash).is_err());
        assert!(refs.add("", &hash).is_err());
    }

    // Property-based tests
    use proptest::prelude::*;

    proptest! {
        #![proptest_config(ProptestConfig {
            cases: 256,
            max_shrink_iters: 10000,
            ..ProptestConfig::default()
        })]

        /// Property 23: Valid ref names are accepted
        #[test]
        fn prop_valid_ref_names_accepted(
            name in "[a-zA-Z0-9_-]{1,50}"
                .prop_filter("no path separators or dots", |n| {
                    !n.contains("..") && !n.contains('/') && !n.contains('\\')
                })
        ) {
            let temp_dir = TempDir::new().unwrap();
            let store = Store::init(temp_dir.path(), Algorithm::Blake3)?;
            let refs = store.refs();

            let hash = Hash::hash_bytes(b"test data");

            // Should successfully add a valid ref name
            let result = refs.add(&name, &hash);
            prop_assert!(
                result.is_ok(),
                "Valid ref name '{}' should be accepted",
                name
            );

            // Should be able to retrieve it
            let retrieved = refs.get(&name)?;
            prop_assert_eq!(retrieved, Some(hash), "Should retrieve the same hash");
        }
    }
}
