//! # Castor Core
//!
//! A content-addressed file store (CAS) using BLAKE3 hashing.
//!
//! This library provides the core functionality for storing and retrieving files and
//! directories by their cryptographic hash. Objects are stored immutably with stable
//! content IDs, using a tree-based directory representation.
//!
//! ## Features
//!
//! - Content-addressed storage: files/dirs stored by hash
//! - Immutable objects with stable content IDs
//! - Tree-based directory representation
//! - Garbage collection for unreferenced objects
//! - Named references (refs) as GC roots
//!
//! ## Example
//!
//! ```no_run
//! use casq_core::{Store, Algorithm};
//! use std::path::Path;
//!
//! # fn main() -> Result<(), Box<dyn std::error::Error>> {
//! // Initialize a new store
//! let store = Store::init("./my-store", Algorithm::Blake3)?;
//!
//! // Add a file or directory
//! let hash = store.add_path(Path::new("./my-data"))?;
//!
//! // Create a reference to the root hash
//! store.refs().add("backup", &hash)?;
//!
//! // Garbage collect unreferenced objects
//! let stats = store.gc(false)?;
//! println!("Deleted {} objects", stats.objects_deleted);
//!
//! // Materialize back to filesystem
//! store.materialize(&hash, Path::new("./restored"))?;
//! # Ok(())
//! # }
//! ```

mod error;
mod gc;
mod hash;
mod object;
mod refs;
mod store;
mod tree;
mod walk;

pub use error::{Error, Result};
pub use gc::GcStats;
pub use hash::{Algorithm, Hash};
pub use object::{ObjectHeader, ObjectType};
pub use refs::RefManager;
pub use store::Store;
pub use tree::{EntryType, FileMode, TreeEntry};
