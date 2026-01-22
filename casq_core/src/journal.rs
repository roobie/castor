//! Operation journal for tracking add operations.

use crate::error::{Error, Result};
use crate::hash::Hash;
use std::collections::HashSet;
use std::fs::{File, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::{Path, PathBuf};

/// A journal entry recording an operation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct JournalEntry {
    /// Unix timestamp when the operation occurred.
    pub timestamp: i64,
    /// Operation type (e.g., "add").
    pub operation: String,
    /// Hash of the object.
    pub hash: Hash,
    /// Original path that was added.
    pub path: String,
    /// Additional metadata (e.g., "entries=15,size=1024").
    pub metadata: String,
}

impl JournalEntry {
    /// Create a new journal entry.
    pub fn new(
        timestamp: i64,
        operation: String,
        hash: Hash,
        path: String,
        metadata: String,
    ) -> Self {
        Self {
            timestamp,
            operation,
            hash,
            path,
            metadata,
        }
    }

    /// Serialize the entry to a pipe-delimited line.
    pub fn to_line(&self) -> String {
        format!(
            "{}|{}|{}|{}|{}",
            self.timestamp, self.operation, self.hash, self.path, self.metadata
        )
    }

    /// Parse a journal entry from a pipe-delimited line.
    pub fn from_line(line: &str) -> Result<Self> {
        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() != 5 {
            return Err(Error::invalid_hash(format!(
                "Invalid journal entry format: expected 5 fields, got {}",
                parts.len()
            )));
        }

        let timestamp = parts[0].parse::<i64>().map_err(|_| {
            Error::invalid_hash(format!("Invalid timestamp in journal entry: {}", parts[0]))
        })?;

        let operation = parts[1].to_string();

        let hash = Hash::from_hex(parts[2]).map_err(|_| {
            Error::invalid_hash(format!("Invalid hash in journal entry: {}", parts[2]))
        })?;

        let path = parts[3].to_string();
        let metadata = parts[4].to_string();

        Ok(Self {
            timestamp,
            operation,
            hash,
            path,
            metadata,
        })
    }
}

/// Journal for tracking operations.
#[derive(Debug)]
pub struct Journal {
    path: PathBuf,
}

impl Journal {
    /// Open or create a journal at the given path.
    pub fn open<P: AsRef<Path>>(path: P) -> Result<Self> {
        let path = path.as_ref().to_path_buf();

        // Create the file if it doesn't exist
        if !path.exists() {
            File::create(&path)?;
        }

        Ok(Self { path })
    }

    /// Append an entry to the journal.
    pub fn append(&self, entry: &JournalEntry) -> Result<()> {
        let mut file = OpenOptions::new().append(true).open(&self.path)?;
        writeln!(file, "{}", entry.to_line())?;
        file.flush()?;
        Ok(())
    }

    /// Read the most recent N entries from the journal.
    pub fn read_recent(&self, count: usize) -> Result<Vec<JournalEntry>> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }

        let file = File::open(&self.path)?;
        let reader = BufReader::new(file);

        // Read all lines
        let mut entries = Vec::new();
        for line in reader.lines() {
            let line = line?;
            let line = line.trim();
            if line.is_empty() {
                continue;
            }

            if let Ok(entry) = JournalEntry::from_line(line) {
                entries.push(entry);
            }
        }

        // Return the last N entries
        if count >= entries.len() {
            Ok(entries)
        } else {
            Ok(entries[entries.len() - count..].to_vec())
        }
    }

    /// Find journal entries for orphaned objects.
    ///
    /// Takes a set of reachable hashes and returns entries whose hashes
    /// are NOT in the reachable set.
    pub fn find_orphans(&self, reachable: &HashSet<Hash>) -> Result<Vec<JournalEntry>> {
        if !self.path.exists() {
            return Ok(Vec::new());
        }

        let file = File::open(&self.path)?;
        let reader = BufReader::new(file);

        let mut orphaned = Vec::new();
        for line in reader.lines() {
            let line = line?;
            let line = line.trim();
            if line.is_empty() {
                continue;
            }

            if let Ok(entry) = JournalEntry::from_line(line) {
                if !reachable.contains(&entry.hash) {
                    orphaned.push(entry);
                }
            }
        }

        Ok(orphaned)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::hash::Hash;
    use tempfile::TempDir;

    #[test]
    fn test_journal_entry_serialization() {
        let hash = Hash::hash_bytes(b"test");
        let entry = JournalEntry::new(
            1737556252,
            "add".to_string(),
            hash,
            "/home/user/data".to_string(),
            "entries=15,size=1024".to_string(),
        );

        let line = entry.to_line();
        let parsed = JournalEntry::from_line(&line).unwrap();

        assert_eq!(entry, parsed);
    }

    #[test]
    fn test_journal_entry_invalid_format() {
        let result = JournalEntry::from_line("invalid|format");
        assert!(result.is_err());
    }

    #[test]
    fn test_journal_open_creates_file() {
        let temp_dir = TempDir::new().unwrap();
        let journal_path = temp_dir.path().join("journal");

        assert!(!journal_path.exists());

        Journal::open(&journal_path).unwrap();

        assert!(journal_path.exists());
    }

    #[test]
    fn test_journal_append() {
        let temp_dir = TempDir::new().unwrap();
        let journal_path = temp_dir.path().join("journal");
        let journal = Journal::open(&journal_path).unwrap();

        let hash = Hash::hash_bytes(b"test");
        let entry = JournalEntry::new(
            1737556252,
            "add".to_string(),
            hash,
            "/test/path".to_string(),
            "entries=5".to_string(),
        );

        journal.append(&entry).unwrap();

        // Verify file contains the entry
        let content = std::fs::read_to_string(&journal_path).unwrap();
        assert!(content.contains(&entry.to_line()));
    }

    #[test]
    fn test_journal_read_recent() {
        let temp_dir = TempDir::new().unwrap();
        let journal_path = temp_dir.path().join("journal");
        let journal = Journal::open(&journal_path).unwrap();

        // Add multiple entries
        for i in 0..10 {
            let hash = Hash::hash_bytes(format!("test{}", i).as_bytes());
            let entry = JournalEntry::new(
                1737556252 + i,
                "add".to_string(),
                hash,
                format!("/path/{}", i),
                format!("entries={}", i),
            );
            journal.append(&entry).unwrap();
        }

        // Read last 3 entries
        let recent = journal.read_recent(3).unwrap();
        assert_eq!(recent.len(), 3);
        assert_eq!(recent[0].timestamp, 1737556252 + 7);
        assert_eq!(recent[1].timestamp, 1737556252 + 8);
        assert_eq!(recent[2].timestamp, 1737556252 + 9);
    }

    #[test]
    fn test_journal_read_recent_more_than_available() {
        let temp_dir = TempDir::new().unwrap();
        let journal_path = temp_dir.path().join("journal");
        let journal = Journal::open(&journal_path).unwrap();

        // Add 3 entries
        for i in 0..3 {
            let hash = Hash::hash_bytes(format!("test{}", i).as_bytes());
            let entry = JournalEntry::new(
                1737556252 + i,
                "add".to_string(),
                hash,
                format!("/path/{}", i),
                format!("entries={}", i),
            );
            journal.append(&entry).unwrap();
        }

        // Request 10 entries (more than available)
        let recent = journal.read_recent(10).unwrap();
        assert_eq!(recent.len(), 3);
    }

    #[test]
    fn test_journal_find_orphans() {
        let temp_dir = TempDir::new().unwrap();
        let journal_path = temp_dir.path().join("journal");
        let journal = Journal::open(&journal_path).unwrap();

        // Add entries
        let hash1 = Hash::hash_bytes(b"test1");
        let hash2 = Hash::hash_bytes(b"test2");
        let hash3 = Hash::hash_bytes(b"test3");

        let entry1 = JournalEntry::new(
            1737556252,
            "add".to_string(),
            hash1,
            "/path/1".to_string(),
            "entries=1".to_string(),
        );
        let entry2 = JournalEntry::new(
            1737556253,
            "add".to_string(),
            hash2,
            "/path/2".to_string(),
            "entries=2".to_string(),
        );
        let entry3 = JournalEntry::new(
            1737556254,
            "add".to_string(),
            hash3,
            "/path/3".to_string(),
            "entries=3".to_string(),
        );

        journal.append(&entry1).unwrap();
        journal.append(&entry2).unwrap();
        journal.append(&entry3).unwrap();

        // Mark hash1 and hash2 as reachable
        let mut reachable = HashSet::new();
        reachable.insert(hash1);
        reachable.insert(hash2);

        // Find orphans (should only be hash3)
        let orphans = journal.find_orphans(&reachable).unwrap();
        assert_eq!(orphans.len(), 1);
        assert_eq!(orphans[0].hash, hash3);
    }

    #[test]
    fn test_journal_empty_file() {
        let temp_dir = TempDir::new().unwrap();
        let journal_path = temp_dir.path().join("journal");
        let journal = Journal::open(&journal_path).unwrap();

        let recent = journal.read_recent(10).unwrap();
        assert_eq!(recent.len(), 0);

        let reachable = HashSet::new();
        let orphans = journal.find_orphans(&reachable).unwrap();
        assert_eq!(orphans.len(), 0);
    }
}
