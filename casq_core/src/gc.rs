//! Garbage collection.

use crate::error::Result;
use crate::hash::Hash;
use crate::object::ObjectType;
use crate::store::Store;
use std::collections::HashSet;
use std::fs;

/// Statistics from a garbage collection run.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct GcStats {
    /// Number of objects deleted.
    pub objects_deleted: usize,
    /// Bytes freed.
    pub bytes_freed: u64,
}

impl Store {
    /// Run garbage collection.
    ///
    /// Walks from all refs to mark reachable objects, then deletes unreachable objects.
    /// If `dry_run` is true, reports what would be deleted without actually deleting.
    pub fn gc(&self, dry_run: bool) -> Result<GcStats> {
        // Mark phase: collect all reachable objects
        let reachable = self.mark_reachable()?;

        // Sweep phase: delete unreachable objects
        self.sweep(&reachable, dry_run)
    }

    /// Mark phase: traverse from all refs and collect reachable objects.
    fn mark_reachable(&self) -> Result<HashSet<Hash>> {
        let mut reachable = HashSet::new();

        // Get all refs
        let refs = self.refs().list()?;

        // Traverse from each ref
        for (_name, hash) in refs {
            self.mark_object(&hash, &mut reachable)?;
        }

        Ok(reachable)
    }

    /// Recursively mark an object and its children as reachable.
    fn mark_object(&self, hash: &Hash, reachable: &mut HashSet<Hash>) -> Result<()> {
        // Already visited
        if reachable.contains(hash) {
            return Ok(());
        }

        // Check if object exists
        let obj_path = self.object_path(hash);
        if !obj_path.exists() {
            // Object referenced by ref but doesn't exist - skip
            return Ok(());
        }

        // Mark as reachable
        reachable.insert(*hash);

        // If it's a tree, recursively mark children
        let header = self.read_object_header(&obj_path)?;
        if header.object_type == ObjectType::Tree {
            let tree = self.get_tree(hash)?;
            for entry in tree {
                self.mark_object(&entry.hash, reachable)?;
            }
        }

        Ok(())
    }

    /// Sweep phase: delete unreachable objects.
    fn sweep(&self, reachable: &HashSet<Hash>, dry_run: bool) -> Result<GcStats> {
        let mut stats = GcStats {
            objects_deleted: 0,
            bytes_freed: 0,
        };

        let objects_dir = self.root().join("objects").join(self.algorithm().as_str());
        if !objects_dir.exists() {
            return Ok(stats);
        }

        // Walk all shard directories
        for shard_entry in fs::read_dir(&objects_dir)? {
            let shard_entry = shard_entry?;
            let shard_path = shard_entry.path();

            if !shard_path.is_dir() {
                continue;
            }

            // Walk all objects in shard
            for obj_entry in fs::read_dir(&shard_path)? {
                let obj_entry = obj_entry?;
                let obj_path = obj_entry.path();

                if !obj_path.is_file() {
                    continue;
                }

                // Parse hash from path
                let prefix = shard_path
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("");
                let suffix = obj_path.file_name().and_then(|n| n.to_str()).unwrap_or("");

                let hash_str = format!("{}{}", prefix, suffix);
                if let Ok(hash) = Hash::from_hex(&hash_str) {
                    // If not reachable, delete it
                    if !reachable.contains(&hash) {
                        let metadata = fs::metadata(&obj_path)?;
                        stats.bytes_freed += metadata.len();
                        stats.objects_deleted += 1;

                        if !dry_run {
                            fs::remove_file(&obj_path)?;
                        }
                    }
                }
            }

            // Remove empty shard directories (only if not dry run)
            if !dry_run
                && let Ok(mut entries) = fs::read_dir(&shard_path)
                && entries.next().is_none()
            {
                let _ = fs::remove_dir(&shard_path);
            }
        }

        Ok(stats)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hash::Algorithm;
    use tempfile::TempDir;

    #[test]
    fn test_gc_empty_store() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        let stats = store.gc(false).unwrap();
        assert_eq!(stats.objects_deleted, 0);
        assert_eq!(stats.bytes_freed, 0);
    }

    #[test]
    fn test_gc_with_ref() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create a blob and reference it
        let hash = store.put_blob(b"test data".as_ref()).unwrap();
        store.refs().add("myref", &hash).unwrap();

        // GC should not delete referenced object
        let stats = store.gc(false).unwrap();
        assert_eq!(stats.objects_deleted, 0);
    }

    #[test]
    fn test_gc_unreferenced_blob() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create a blob without referencing it
        let hash = store.put_blob(b"orphan data".as_ref()).unwrap();

        // Verify object exists
        assert!(store.object_path(&hash).exists());

        // GC should delete unreferenced object
        let stats = store.gc(false).unwrap();
        assert_eq!(stats.objects_deleted, 1);
        assert!(stats.bytes_freed > 0);

        // Verify object was deleted
        assert!(!store.object_path(&hash).exists());
    }

    #[test]
    fn test_gc_dry_run() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create orphan blob
        let hash = store.put_blob(b"orphan".as_ref()).unwrap();

        // Dry run should report but not delete
        let stats = store.gc(true).unwrap();
        assert_eq!(stats.objects_deleted, 1);
        assert!(stats.bytes_freed > 0);

        // Object should still exist
        assert!(store.object_path(&hash).exists());

        // Actual GC should delete
        let stats2 = store.gc(false).unwrap();
        assert_eq!(stats2.objects_deleted, 1);
        assert!(!store.object_path(&hash).exists());
    }

    #[test]
    fn test_gc_tree_reachability() {
        use crate::tree::{EntryType, TreeEntry, file_modes};

        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create blobs
        let blob1 = store.put_blob(b"file1".as_ref()).unwrap();
        let blob2 = store.put_blob(b"file2".as_ref()).unwrap();
        let orphan = store.put_blob(b"orphan".as_ref()).unwrap();

        // Create tree referencing blob1 and blob2
        let entries = vec![
            TreeEntry::new(
                EntryType::Blob,
                file_modes::REGULAR,
                blob1,
                "file1".to_string(),
            )
            .unwrap(),
            TreeEntry::new(
                EntryType::Blob,
                file_modes::REGULAR,
                blob2,
                "file2".to_string(),
            )
            .unwrap(),
        ];
        let tree = store.put_tree(entries).unwrap();

        // Reference the tree
        store.refs().add("mytree", &tree).unwrap();

        // GC should only delete orphan
        let stats = store.gc(false).unwrap();
        assert_eq!(stats.objects_deleted, 1);

        // Verify tree and its blobs still exist
        assert!(store.object_path(&tree).exists());
        assert!(store.object_path(&blob1).exists());
        assert!(store.object_path(&blob2).exists());
        assert!(!store.object_path(&orphan).exists());
    }

    #[test]
    fn test_gc_after_ref_removed() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create and reference a blob
        let hash = store.put_blob(b"data".as_ref()).unwrap();
        store.refs().add("ref1", &hash).unwrap();

        // GC should not delete
        let stats = store.gc(false).unwrap();
        assert_eq!(stats.objects_deleted, 0);

        // Remove ref
        store.refs().remove("ref1").unwrap();

        // GC should now delete
        let stats = store.gc(false).unwrap();
        assert_eq!(stats.objects_deleted, 1);
        assert!(!store.object_path(&hash).exists());
    }
}
