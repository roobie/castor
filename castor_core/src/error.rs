//! Error types for castor_core.

use std::path::PathBuf;
use thiserror::Error;

/// Result type alias using castor_core's Error type.
pub type Result<T> = std::result::Result<T, Error>;

/// Errors that can occur during store operations.
#[derive(Error, Debug)]
pub enum Error {
    /// I/O error occurred during file operations.
    #[error("I/O error: {source}")]
    Io {
        #[from]
        source: std::io::Error,
    },

    /// Object file is corrupted or invalid.
    #[error("Corrupted object at {path}: {reason}")]
    CorruptedObject { path: PathBuf, reason: String },

    /// Invalid hash format or encoding.
    #[error("Invalid hash: {reason}")]
    InvalidHash { reason: String },

    /// Object not found in store.
    #[error("Object not found: {hash}")]
    ObjectNotFound { hash: String },

    /// Store is invalid or not initialized.
    #[error("Invalid store at {path}: {reason}")]
    InvalidStore { path: PathBuf, reason: String },

    /// Invalid reference name or format.
    #[error("Invalid reference: {reason}")]
    InvalidRef { reason: String },

    /// Reference not found.
    #[error("Reference not found: {name}")]
    RefNotFound { name: String },

    /// Invalid object type.
    #[error("Invalid object type: expected {expected}, got {got}")]
    InvalidObjectType { expected: String, got: String },

    /// Path already exists (for materialization).
    #[error("Path already exists: {path}")]
    PathExists { path: PathBuf },

    /// UTF-8 encoding error.
    #[error("UTF-8 error: {source}")]
    Utf8Error {
        #[from]
        source: std::str::Utf8Error,
    },

    /// Invalid tree entry.
    #[error("Invalid tree entry: {reason}")]
    InvalidTreeEntry { reason: String },

    /// Unsupported algorithm.
    #[error("Unsupported algorithm: {algorithm}")]
    UnsupportedAlgorithm { algorithm: String },
}

impl Error {
    /// Create a CorruptedObject error.
    pub fn corrupted_object(path: impl Into<PathBuf>, reason: impl Into<String>) -> Self {
        Error::CorruptedObject {
            path: path.into(),
            reason: reason.into(),
        }
    }

    /// Create an InvalidHash error.
    pub fn invalid_hash(reason: impl Into<String>) -> Self {
        Error::InvalidHash {
            reason: reason.into(),
        }
    }

    /// Create an ObjectNotFound error.
    pub fn object_not_found(hash: impl Into<String>) -> Self {
        Error::ObjectNotFound { hash: hash.into() }
    }

    /// Create an InvalidStore error.
    pub fn invalid_store(path: impl Into<PathBuf>, reason: impl Into<String>) -> Self {
        Error::InvalidStore {
            path: path.into(),
            reason: reason.into(),
        }
    }

    /// Create an InvalidRef error.
    pub fn invalid_ref(reason: impl Into<String>) -> Self {
        Error::InvalidRef {
            reason: reason.into(),
        }
    }

    /// Create a RefNotFound error.
    pub fn ref_not_found(name: impl Into<String>) -> Self {
        Error::RefNotFound { name: name.into() }
    }

    /// Create an InvalidObjectType error.
    pub fn invalid_object_type(expected: impl Into<String>, got: impl Into<String>) -> Self {
        Error::InvalidObjectType {
            expected: expected.into(),
            got: got.into(),
        }
    }

    /// Create a PathExists error.
    pub fn path_exists(path: impl Into<PathBuf>) -> Self {
        Error::PathExists { path: path.into() }
    }

    /// Create an InvalidTreeEntry error.
    pub fn invalid_tree_entry(reason: impl Into<String>) -> Self {
        Error::InvalidTreeEntry {
            reason: reason.into(),
        }
    }

    /// Create an UnsupportedAlgorithm error.
    pub fn unsupported_algorithm(algorithm: impl Into<String>) -> Self {
        Error::UnsupportedAlgorithm {
            algorithm: algorithm.into(),
        }
    }
}

// Additional From implementations for external error types

impl From<tempfile::PersistError> for Error {
    fn from(err: tempfile::PersistError) -> Self {
        Error::Io { source: err.error }
    }
}

impl From<ignore::Error> for Error {
    fn from(err: ignore::Error) -> Self {
        // ignore::Error can wrap an io::Error or be a path error
        match err.io_error() {
            Some(io_err) => Error::Io {
                source: std::io::Error::new(io_err.kind(), io_err.to_string()),
            },
            None => Error::Io {
                source: std::io::Error::other(err.to_string()),
            },
        }
    }
}
