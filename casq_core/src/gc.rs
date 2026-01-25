//! Garbage collection.

use crate::error::Result;
use crate::hash::Hash;
use crate::object::ObjectType;
use crate::store::Store;
use serde::Serialize;
use std::collections::HashSet;
use std::fs;

/// Statistics from a garbage collection run.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GcStats {
    /// Number of objects deleted.
    pub objects_deleted: usize,
    /// Bytes freed.
    pub bytes_freed: u64,
}

/// Information about an orphaned object (blob or tree).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct OrphanRoot {
    /// Hash of the orphaned object.
    pub hash: Hash,
    /// Type of object (blob, tree, or chunk_list).
    pub object_type: ObjectType,
    /// Number of entries (only for trees, None for blobs).
    pub entry_count: Option<usize>,
    /// Approximate size in bytes (on-disk size).
    pub approx_size: u64,
}

type EntryInfo = (Hash, ObjectType, Option<usize>, u64);
type GcResult = (Vec<EntryInfo>, HashSet<Hash>);

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
    pub(crate) fn mark_reachable(&self) -> Result<HashSet<Hash>> {
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
        match header.object_type {
            ObjectType::Tree => {
                let tree = self.get_tree(hash)?;
                for entry in tree {
                    self.mark_object(&entry.hash, reachable)?;
                }
            }
            ObjectType::ChunkList => {
                // Mark all chunks as reachable
                use crate::object::ChunkList;
                let chunk_list_payload = self.read_object_payload(&obj_path, header.payload_len)?;
                let chunk_list = ChunkList::decode(&chunk_list_payload)?;
                for chunk_entry in &chunk_list.chunks {
                    self.mark_object(&chunk_entry.hash, reachable)?;
                }
            }
            ObjectType::Blob => {
                // Blobs have no children
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

    /// Find orphaned object roots.
    ///
    /// Returns a list of unreferenced blobs and trees that are not referenced by other
    /// unreferenced objects. For trees, only returns "root" trees (not child trees).
    pub fn find_orphan_roots(&self) -> Result<Vec<OrphanRoot>> {
        // Mark phase: collect all reachable objects
        let reachable = self.mark_reachable()?;

        // Scan unreachable objects
        let (unreachable_objects, child_refs) = self.scan_unreachable(&reachable)?;

        // Filter for orphan roots (objects not referenced by other unreachable objects)
        self.filter_orphan_roots(unreachable_objects, &child_refs)
    }

    /// Scan all objects and identify unreachable objects and their child references.
    ///
    /// Returns:
    /// - Vec of (hash, object_type, entry_count, size) for unreachable blob/tree objects
    /// - HashSet of all hashes referenced by unreachable trees
    fn scan_unreachable(&self, reachable: &HashSet<Hash>) -> Result<GcResult> {
        let mut unreachable_objects = Vec::new();
        let mut child_refs = HashSet::new();

        let objects_dir = self.root().join("objects").join(self.algorithm().as_str());
        if !objects_dir.exists() {
            return Ok((unreachable_objects, child_refs));
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
                    // Skip reachable objects
                    if reachable.contains(&hash) {
                        continue;
                    }

                    // Check object type and collect based on type
                    if let Ok(header) = self.read_object_header(&obj_path) {
                        // Get size
                        let size = fs::metadata(&obj_path)?.len();

                        match header.object_type {
                            ObjectType::Tree => {
                                // Get tree entries to count them and collect child refs
                                if let Ok(entries) = self.get_tree(&hash) {
                                    let entry_count = entries.len();

                                    // Collect all child hashes from this unreachable tree
                                    for entry in &entries {
                                        child_refs.insert(entry.hash);
                                    }

                                    unreachable_objects.push((
                                        hash,
                                        ObjectType::Tree,
                                        Some(entry_count),
                                        size,
                                    ));
                                }
                            }
                            ObjectType::Blob => {
                                // Include blobs (they have no children)
                                unreachable_objects.push((hash, ObjectType::Blob, None, size));
                            }
                            ObjectType::ChunkList => {
                                // Skip ChunkLists - they are internal implementation details
                            }
                        }
                    }
                }
            }
        }

        Ok((unreachable_objects, child_refs))
    }

    /// Filter unreachable objects to find orphan roots.
    ///
    /// An orphan root is an unreachable object (blob or tree) that is NOT referenced
    /// by any other unreachable object. For trees, this means top-level trees that were
    /// added without refs. For blobs, this means any unreferenced blob.
    fn filter_orphan_roots(
        &self,
        unreachable_objects: Vec<(Hash, ObjectType, Option<usize>, u64)>,
        child_refs: &HashSet<Hash>,
    ) -> Result<Vec<OrphanRoot>> {
        let mut orphan_roots = Vec::new();

        for (hash, object_type, entry_count, approx_size) in unreachable_objects {
            // If this object is not referenced by any other unreachable object,
            // it's an orphan root
            if !child_refs.contains(&hash) {
                orphan_roots.push(OrphanRoot {
                    hash,
                    object_type,
                    entry_count,
                    approx_size,
                });
            }
        }

        Ok(orphan_roots)
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

    #[test]
    fn test_find_orphans_empty_store() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        let orphans = store.find_orphan_roots().unwrap();
        assert_eq!(orphans.len(), 0);
    }

    #[test]
    fn test_find_orphans_unreferenced_tree() {
        use crate::tree::{EntryType, TreeEntry, file_modes};

        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create a blob
        let blob = store.put_blob(b"file content".as_ref()).unwrap();

        // Create a tree without referencing it
        let entries = vec![
            TreeEntry::new(
                EntryType::Blob,
                file_modes::REGULAR,
                blob,
                "file.txt".to_string(),
            )
            .unwrap(),
        ];
        let tree_hash = store.put_tree(entries).unwrap();

        // Should find the orphaned tree
        let orphans = store.find_orphan_roots().unwrap();
        assert_eq!(orphans.len(), 1);
        assert_eq!(orphans[0].hash, tree_hash);
        assert_eq!(orphans[0].object_type, ObjectType::Tree);
        assert_eq!(orphans[0].entry_count, Some(1));
        assert!(orphans[0].approx_size > 0);
    }

    #[test]
    fn test_find_orphans_referenced_tree() {
        use crate::tree::{EntryType, TreeEntry, file_modes};

        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create a blob
        let blob = store.put_blob(b"file content".as_ref()).unwrap();

        // Create a tree and reference it
        let entries = vec![
            TreeEntry::new(
                EntryType::Blob,
                file_modes::REGULAR,
                blob,
                "file.txt".to_string(),
            )
            .unwrap(),
        ];
        let tree_hash = store.put_tree(entries).unwrap();
        store.refs().add("mytree", &tree_hash).unwrap();

        // Should NOT find any orphans (tree is referenced)
        let orphans = store.find_orphan_roots().unwrap();
        assert_eq!(orphans.len(), 0);
    }

    #[test]
    fn test_find_orphans_nested_unreferenced_trees() {
        use crate::tree::{EntryType, TreeEntry, file_modes};

        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create a blob
        let blob = store.put_blob(b"nested file".as_ref()).unwrap();

        // Create a subtree
        let subtree_entries = vec![
            TreeEntry::new(
                EntryType::Blob,
                file_modes::REGULAR,
                blob,
                "nested.txt".to_string(),
            )
            .unwrap(),
        ];
        let subtree_hash = store.put_tree(subtree_entries).unwrap();

        // Create a parent tree referencing the subtree
        let parent_entries = vec![
            TreeEntry::new(
                EntryType::Tree,
                file_modes::DIRECTORY,
                subtree_hash,
                "subdir".to_string(),
            )
            .unwrap(),
        ];
        let parent_hash = store.put_tree(parent_entries).unwrap();

        // Neither tree is referenced, but subtree is referenced by parent
        // So only parent should be an orphan root
        let orphans = store.find_orphan_roots().unwrap();
        assert_eq!(orphans.len(), 1);
        assert_eq!(orphans[0].hash, parent_hash);
        assert_eq!(orphans[0].object_type, ObjectType::Tree);
    }

    #[test]
    fn test_find_orphans_includes_blobs() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create orphaned blobs
        let hash1 = store.put_blob(b"orphan1".as_ref()).unwrap();
        let hash2 = store.put_blob(b"orphan2".as_ref()).unwrap();

        // Should find both blob orphans
        let orphans = store.find_orphan_roots().unwrap();
        assert_eq!(orphans.len(), 2);
        assert!(
            orphans
                .iter()
                .any(|o| o.hash == hash1 && o.object_type == ObjectType::Blob)
        );
        assert!(
            orphans
                .iter()
                .any(|o| o.hash == hash2 && o.object_type == ObjectType::Blob)
        );
        assert!(orphans.iter().all(|o| o.entry_count.is_none()));
    }

    #[test]
    fn test_find_orphans_mixed_blobs_and_trees() {
        use crate::tree::{EntryType, TreeEntry, file_modes};

        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create orphaned blobs
        let blob1 = store.put_blob(b"orphan blob 1".as_ref()).unwrap();
        let blob2 = store.put_blob(b"orphan blob 2".as_ref()).unwrap();

        // Create orphaned tree
        let tree_blob = store.put_blob(b"tree content".as_ref()).unwrap();
        let tree_hash = store
            .put_tree(vec![
                TreeEntry::new(
                    EntryType::Blob,
                    file_modes::REGULAR,
                    tree_blob,
                    "file.txt".to_string(),
                )
                .unwrap(),
            ])
            .unwrap();

        // Should find all orphans (2 standalone blobs + 1 tree)
        // Note: tree_blob is referenced by the tree, so it won't be an orphan root
        let orphans = store.find_orphan_roots().unwrap();
        assert_eq!(orphans.len(), 3);

        // Check for the two standalone blobs
        assert!(
            orphans
                .iter()
                .any(|o| o.hash == blob1 && o.object_type == ObjectType::Blob)
        );
        assert!(
            orphans
                .iter()
                .any(|o| o.hash == blob2 && o.object_type == ObjectType::Blob)
        );

        // Check for the tree
        assert!(
            orphans
                .iter()
                .any(|o| o.hash == tree_hash && o.object_type == ObjectType::Tree)
        );

        // Verify blobs have no entry_count, tree has entry_count
        let blob_orphans: Vec<_> = orphans
            .iter()
            .filter(|o| o.object_type == ObjectType::Blob)
            .collect();
        assert_eq!(blob_orphans.len(), 2);
        assert!(blob_orphans.iter().all(|o| o.entry_count.is_none()));

        let tree_orphans: Vec<_> = orphans
            .iter()
            .filter(|o| o.object_type == ObjectType::Tree)
            .collect();
        assert_eq!(tree_orphans.len(), 1);
        assert_eq!(tree_orphans[0].entry_count, Some(1));
    }

    #[test]
    fn test_find_orphans_multiple_orphan_roots() {
        use crate::tree::{EntryType, TreeEntry, file_modes};

        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path(), Algorithm::Blake3).unwrap();

        // Create first orphan tree
        let blob1 = store.put_blob(b"file1".as_ref()).unwrap();
        let tree1 = store
            .put_tree(vec![
                TreeEntry::new(
                    EntryType::Blob,
                    file_modes::REGULAR,
                    blob1,
                    "file1.txt".to_string(),
                )
                .unwrap(),
            ])
            .unwrap();

        // Create second orphan tree
        let blob2 = store.put_blob(b"file2".as_ref()).unwrap();
        let tree2 = store
            .put_tree(vec![
                TreeEntry::new(
                    EntryType::Blob,
                    file_modes::REGULAR,
                    blob2,
                    "file2.txt".to_string(),
                )
                .unwrap(),
            ])
            .unwrap();

        // Should find both orphan roots
        let orphans = store.find_orphan_roots().unwrap();
        assert_eq!(orphans.len(), 2);

        let orphan_hashes: Vec<_> = orphans.iter().map(|o| o.hash).collect();
        assert!(orphan_hashes.contains(&tree1));
        assert!(orphan_hashes.contains(&tree2));
    }

    // Property-based tests
    use proptest::prelude::*;

    proptest! {
        #![proptest_config(ProptestConfig {
            cases: 32,  // Expensive tests - reduced case count
            max_shrink_iters: 5000,
            ..ProptestConfig::default()
        })]

        /// Property 20: GC preserves referenced objects
        #[test]
        fn prop_gc_preserves_referenced(_seed in any::<u64>()) {
            let temp_dir = TempDir::new().unwrap();
            let store = Store::init(temp_dir.path(), Algorithm::Blake3)?;

            // Create referenced blob
            let ref_data = b"referenced content";
            let referenced_hash = store.put_blob(&ref_data[..])?;
            store.refs().add("test-ref", &referenced_hash)?;

            // Create unreferenced blob
            let unref_data = b"unreferenced content";
            let _unreferenced_hash = store.put_blob(&unref_data[..])?;

            // Run GC
            let stats = store.gc(false)?;

            // Referenced object must still exist
            prop_assert!(
                store.get_blob(&referenced_hash).is_ok(),
                "GC deleted a referenced object"
            );

            // Should have deleted at least one object (the unreferenced one)
            prop_assert!(
                stats.objects_deleted > 0,
                "GC should delete unreferenced objects"
            );
        }

        /// Property 21: GC deletes unreferenced objects
        #[test]
        fn prop_gc_deletes_unreferenced(_seed in any::<u64>()) {
            let temp_dir = TempDir::new().unwrap();
            let store = Store::init(temp_dir.path(), Algorithm::Blake3)?;

            // Create referenced blob
            let ref_data = b"referenced";
            let referenced_hash = store.put_blob(&ref_data[..])?;
            store.refs().add("keep", &referenced_hash)?;

            // Create unreferenced blob
            let unref_data = b"unreferenced";
            let unreferenced_hash = store.put_blob(&unref_data[..])?;

            // Run GC
            store.gc(false)?;

            // Unreferenced object must be deleted
            prop_assert!(
                store.get_blob(&unreferenced_hash).is_err(),
                "GC failed to delete unreferenced object"
            );

            // Referenced object must still exist
            prop_assert!(
                store.get_blob(&referenced_hash).is_ok(),
                "GC deleted referenced object"
            );
        }

        /// Property 22: GC is idempotent
        #[test]
        fn prop_gc_idempotent(_seed in any::<u64>()) {
            let temp_dir = TempDir::new().unwrap();
            let store = Store::init(temp_dir.path(), Algorithm::Blake3)?;

            // Create a referenced blob
            let ref_hash = store.put_blob(b"referenced".as_ref())?;
            store.refs().add("keep", &ref_hash)?;

            // Create an unreferenced blob
            store.put_blob(b"unreferenced".as_ref())?;

            // Run GC twice
            let stats1 = store.gc(false)?;
            let stats2 = store.gc(false)?;

            // Second run should delete nothing
            prop_assert_eq!(
                stats2.objects_deleted,
                0,
                "GC is not idempotent - deleted objects on second run"
            );

            // First run should have deleted something
            prop_assert!(
                stats1.objects_deleted > 0,
                "First GC run should delete unreferenced objects"
            );
        }
    }
}
