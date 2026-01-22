//! Filesystem walking and object creation.

use crate::error::{Error, Result};
use crate::hash::Hash;
use crate::journal::JournalEntry;
use crate::store::Store;
use crate::tree::{EntryType, TreeEntry, file_modes};
use std::fs;
use std::path::Path;

impl Store {
    /// Add a file or directory to the store.
    ///
    /// If the path is a file, creates a blob and returns its hash.
    /// If the path is a directory, recursively creates trees and returns the root tree hash.
    /// Records the operation in the journal.
    pub fn add_path(&self, path: &Path) -> Result<Hash> {
        if !path.exists() {
            return Err(Error::Io {
                source: std::io::Error::new(
                    std::io::ErrorKind::NotFound,
                    format!("Path does not exist: {}", path.display()),
                ),
            });
        }

        let metadata = fs::metadata(path)?;

        let hash = if metadata.is_file() {
            self.add_file(path)?
        } else if metadata.is_dir() {
            self.add_directory(path)?
        } else {
            return Err(Error::invalid_hash(format!(
                "Unsupported file type: {}",
                path.display()
            )));
        };

        // Append to journal
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs() as i64;

        // Get metadata for journal
        let (entry_count, approx_size) = if metadata.is_file() {
            (1, metadata.len())
        } else {
            // For directories, get tree entry count and object size
            let tree = self.get_tree(&hash)?;
            let obj_path = self.object_path(&hash);
            let obj_size = fs::metadata(&obj_path)?.len();
            (tree.len(), obj_size)
        };

        let journal_metadata = format!("entries={},size={}", entry_count, approx_size);
        let journal_entry = JournalEntry::new(
            timestamp,
            "add".to_string(),
            hash,
            path.display().to_string(),
            journal_metadata,
        );

        self.journal().append(&journal_entry)?;

        Ok(hash)
    }

    /// Add a single file as a blob.
    fn add_file(&self, path: &Path) -> Result<Hash> {
        let file = fs::File::open(path)?;
        self.put_blob(file)
    }

    /// Add a directory recursively as a tree.
    fn add_directory(&self, path: &Path) -> Result<Hash> {
        let mut entries = Vec::new();

        // Use ignore crate to respect .gitignore
        let walker = ignore::WalkBuilder::new(path)
            .max_depth(Some(1)) // Only immediate children
            .hidden(false) // Include hidden files
            .git_ignore(true) // Respect .gitignore
            .build();

        for entry in walker {
            let entry = entry?;
            let entry_path = entry.path();

            // Skip the directory itself
            if entry_path == path {
                continue;
            }

            let metadata = entry_path.metadata()?;
            let file_name = entry_path
                .file_name()
                .and_then(|n| n.to_str())
                .ok_or_else(|| {
                    Error::invalid_hash(format!("Invalid filename: {}", entry_path.display()))
                })?
                .to_string();

            if metadata.is_file() {
                let mode = get_file_mode(&metadata);
                let hash = self.add_file(entry_path)?;
                let tree_entry = TreeEntry::new(EntryType::Blob, mode, hash, file_name)?;
                entries.push(tree_entry);
            } else if metadata.is_dir() {
                // Recursively process subdirectory
                let hash = self.add_directory(entry_path)?;
                let tree_entry =
                    TreeEntry::new(EntryType::Tree, file_modes::DIRECTORY, hash, file_name)?;
                entries.push(tree_entry);
            } else if metadata.is_symlink() {
                // Symlinks not supported in MVP
                return Err(Error::invalid_hash(format!(
                    "Symlinks not supported: {}",
                    entry_path.display()
                )));
            }
        }

        // Create tree from entries
        self.put_tree(entries)
    }
}

/// Get the file mode (permissions) from metadata.
#[cfg(unix)]
fn get_file_mode(metadata: &fs::Metadata) -> u32 {
    use std::os::unix::fs::PermissionsExt;
    let perms = metadata.permissions();
    let mode = perms.mode();

    // Check if executable
    if mode & 0o111 != 0 {
        file_modes::EXECUTABLE
    } else {
        file_modes::REGULAR
    }
}

/// Get the file mode (permissions) from metadata (Windows fallback).
#[cfg(not(unix))]
fn get_file_mode(_metadata: &fs::Metadata) -> u32 {
    // On Windows, default to regular file mode
    file_modes::REGULAR
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hash::Algorithm;
    use std::fs;
    use tempfile::TempDir;

    #[test]
    fn test_add_single_file() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path().join("store"), Algorithm::Blake3).unwrap();

        let test_file = temp_dir.path().join("test.txt");
        fs::write(&test_file, b"hello world").unwrap();

        let hash = store.add_path(&test_file).unwrap();
        let expected = Hash::hash_bytes(b"hello world");
        assert_eq!(hash, expected);
    }

    #[test]
    fn test_add_empty_file() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path().join("store"), Algorithm::Blake3).unwrap();

        let test_file = temp_dir.path().join("empty.txt");
        fs::write(&test_file, b"").unwrap();

        let hash = store.add_path(&test_file).unwrap();
        let expected = Hash::hash_bytes(b"");
        assert_eq!(hash, expected);
    }

    #[test]
    fn test_add_empty_directory() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path().join("store"), Algorithm::Blake3).unwrap();

        let test_dir = temp_dir.path().join("empty_dir");
        fs::create_dir(&test_dir).unwrap();

        let hash = store.add_path(&test_dir).unwrap();
        let tree = store.get_tree(&hash).unwrap();
        assert_eq!(tree.len(), 0);
    }

    #[test]
    fn test_add_directory_with_files() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path().join("store"), Algorithm::Blake3).unwrap();

        let test_dir = temp_dir.path().join("test_dir");
        fs::create_dir(&test_dir).unwrap();
        fs::write(test_dir.join("file1.txt"), b"content1").unwrap();
        fs::write(test_dir.join("file2.txt"), b"content2").unwrap();

        let hash = store.add_path(&test_dir).unwrap();
        let tree = store.get_tree(&hash).unwrap();

        assert_eq!(tree.len(), 2);
        assert_eq!(tree[0].name, "file1.txt");
        assert_eq!(tree[1].name, "file2.txt");
    }

    #[test]
    fn test_add_nested_directories() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path().join("store"), Algorithm::Blake3).unwrap();

        let test_dir = temp_dir.path().join("parent");
        fs::create_dir(&test_dir).unwrap();
        fs::write(test_dir.join("root_file.txt"), b"root").unwrap();

        let sub_dir = test_dir.join("subdir");
        fs::create_dir(&sub_dir).unwrap();
        fs::write(sub_dir.join("sub_file.txt"), b"sub").unwrap();

        let hash = store.add_path(&test_dir).unwrap();
        let tree = store.get_tree(&hash).unwrap();

        assert_eq!(tree.len(), 2);

        // Find the subdirectory entry
        let subdir_entry = tree.iter().find(|e| e.name == "subdir").unwrap();
        assert_eq!(subdir_entry.entry_type, EntryType::Tree);

        // Verify subtree
        let subtree = store.get_tree(&subdir_entry.hash).unwrap();
        assert_eq!(subtree.len(), 1);
        assert_eq!(subtree[0].name, "sub_file.txt");
    }

    #[test]
    fn test_add_nonexistent_path() {
        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path().join("store"), Algorithm::Blake3).unwrap();

        let nonexistent = temp_dir.path().join("nonexistent");
        let result = store.add_path(&nonexistent);
        assert!(result.is_err());
    }

    #[test]
    #[cfg(unix)]
    fn test_executable_file_mode() {
        use std::os::unix::fs::PermissionsExt;

        let temp_dir = TempDir::new().unwrap();
        let store = Store::init(temp_dir.path().join("store"), Algorithm::Blake3).unwrap();

        let test_dir = temp_dir.path().join("test_dir");
        fs::create_dir(&test_dir).unwrap();

        let script = test_dir.join("script.sh");
        fs::write(&script, b"#!/bin/bash\necho hello").unwrap();
        let mut perms = fs::metadata(&script).unwrap().permissions();
        perms.set_mode(0o755);
        fs::set_permissions(&script, perms).unwrap();

        let hash = store.add_path(&test_dir).unwrap();
        let tree = store.get_tree(&hash).unwrap();

        assert_eq!(tree.len(), 1);
        assert_eq!(tree[0].mode, file_modes::EXECUTABLE);
    }
}
