//! Hashing functionality using BLAKE3.

use crate::error::{Error, Result};
use std::fmt;
use std::io::Read;
use std::path::Path;

/// Hash digest size in bytes (BLAKE3 produces 256-bit hashes).
pub const HASH_SIZE: usize = 32;

/// Supported hash algorithms.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Algorithm {
    /// BLAKE3 with 256-bit output.
    Blake3,
}

impl Algorithm {
    /// Returns the string representation of the algorithm (for config files).
    pub fn as_str(&self) -> &'static str {
        match self {
            Algorithm::Blake3 => "blake3-256",
        }
    }

    /// Parse algorithm from string.
    pub fn parse(s: &str) -> Result<Self> {
        match s {
            "blake3-256" => Ok(Algorithm::Blake3),
            _ => Err(Error::unsupported_algorithm(s)),
        }
    }

    /// Returns the algorithm ID byte (for object headers).
    pub fn id(&self) -> u8 {
        match self {
            Algorithm::Blake3 => 1,
        }
    }

    /// Parse algorithm from ID byte.
    pub fn from_id(id: u8) -> Result<Self> {
        match id {
            1 => Ok(Algorithm::Blake3),
            _ => Err(Error::unsupported_algorithm(format!("ID {}", id))),
        }
    }
}

/// A 32-byte BLAKE3 hash digest.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Hash([u8; HASH_SIZE]);

impl Hash {
    /// Create a Hash from raw bytes.
    pub fn from_bytes(bytes: [u8; HASH_SIZE]) -> Self {
        Hash(bytes)
    }

    /// Create a Hash from a hex string (64 hex characters).
    pub fn from_hex(hex_str: &str) -> Result<Self> {
        if hex_str.len() != HASH_SIZE * 2 {
            return Err(Error::invalid_hash(format!(
                "Expected {} hex characters, got {}",
                HASH_SIZE * 2,
                hex_str.len()
            )));
        }

        let bytes =
            hex::decode(hex_str).map_err(|e| Error::invalid_hash(format!("Invalid hex: {}", e)))?;

        let mut hash = [0u8; HASH_SIZE];
        hash.copy_from_slice(&bytes);
        Ok(Hash(hash))
    }

    /// Convert to hex string (64 characters).
    pub fn to_hex(&self) -> String {
        hex::encode(self.0)
    }

    /// Get the first 2 hex characters (for directory sharding).
    pub fn prefix(&self) -> String {
        hex::encode(&self.0[..1])
    }

    /// Get the remaining 62 hex characters (for filename).
    pub fn suffix(&self) -> String {
        hex::encode(&self.0[1..])
    }

    /// Get the raw bytes.
    pub fn as_bytes(&self) -> &[u8; HASH_SIZE] {
        &self.0
    }

    /// Hash raw bytes using BLAKE3.
    pub fn hash_bytes(data: &[u8]) -> Self {
        let hash = blake3::hash(data);
        Hash(*hash.as_bytes())
    }

    /// Hash data from a reader using BLAKE3.
    pub fn hash_reader<R: Read>(mut reader: R) -> Result<Self> {
        let mut hasher = blake3::Hasher::new();
        std::io::copy(&mut reader, &mut hasher)?;
        let hash = hasher.finalize();
        Ok(Hash(*hash.as_bytes()))
    }

    /// Hash a file using BLAKE3.
    pub fn hash_file(path: &Path) -> Result<Self> {
        let file = std::fs::File::open(path)?;
        Self::hash_reader(file)
    }
}

impl fmt::Display for Hash {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.to_hex())
    }
}

impl fmt::Debug for Hash {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Hash({})", self.to_hex())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hash_empty() {
        let hash = Hash::hash_bytes(b"");
        assert_eq!(hash.to_hex().len(), 64);
    }

    #[test]
    fn test_hash_hello_world() {
        let hash = Hash::hash_bytes(b"hello world");
        let hex = hash.to_hex();
        assert_eq!(hex.len(), 64);

        // BLAKE3 of "hello world"
        assert_eq!(
            hex,
            "d74981efa70a0c880b8d8c1985d075dbcbf679b99a5f9914e5aaf96b831a9e24"
        );
    }

    #[test]
    fn test_hash_from_hex_roundtrip() {
        let original = Hash::hash_bytes(b"test data");
        let hex = original.to_hex();
        let parsed = Hash::from_hex(&hex).unwrap();
        assert_eq!(original, parsed);
    }

    #[test]
    fn test_hash_from_hex_invalid_length() {
        assert!(Hash::from_hex("abcd").is_err());
        assert!(Hash::from_hex("").is_err());
    }

    #[test]
    fn test_hash_from_hex_invalid_chars() {
        let invalid = "z".repeat(64);
        assert!(Hash::from_hex(&invalid).is_err());
    }

    #[test]
    fn test_hash_prefix_suffix() {
        let hash = Hash::hash_bytes(b"test");
        let prefix = hash.prefix();
        let suffix = hash.suffix();

        assert_eq!(prefix.len(), 2);
        assert_eq!(suffix.len(), 62);

        // Concatenated should equal full hex
        let full = format!("{}{}", prefix, suffix);
        assert_eq!(full, hash.to_hex());
    }

    #[test]
    fn test_hash_ordering() {
        let hash1 = Hash::hash_bytes(b"a");
        let hash2 = Hash::hash_bytes(b"b");

        // Hashes should be comparable
        assert_ne!(hash1, hash2);
        // Order is deterministic based on bytes
        assert!(hash1 < hash2 || hash1 > hash2);
    }

    #[test]
    fn test_algorithm_conversions() {
        let algo = Algorithm::Blake3;
        assert_eq!(algo.as_str(), "blake3-256");
        assert_eq!(algo.id(), 1);

        assert_eq!(Algorithm::parse("blake3-256").unwrap(), Algorithm::Blake3);
        assert_eq!(Algorithm::from_id(1).unwrap(), Algorithm::Blake3);

        assert!(Algorithm::parse("unknown").is_err());
        assert!(Algorithm::from_id(99).is_err());
    }

    // Property-based tests
    use proptest::prelude::*;

    proptest! {
        #![proptest_config(ProptestConfig {
            cases: 256,
            max_shrink_iters: 10000,
            ..ProptestConfig::default()
        })]

        /// Property 1: Hash determinism - hashing the same data always produces the same hash
        #[test]
        fn prop_hash_deterministic(data: Vec<u8>) {
            let hash1 = Hash::hash_bytes(&data);
            let hash2 = Hash::hash_bytes(&data);
            prop_assert_eq!(hash1, hash2);
        }

        /// Property 2: Hex encoding is bijective - round-trip through hex preserves hash
        #[test]
        fn prop_hex_roundtrip(bytes in prop::array::uniform32(any::<u8>())) {
            let hash = Hash::from_bytes(bytes);
            let hex = hash.to_hex();
            let parsed = Hash::from_hex(&hex)?;
            prop_assert_eq!(hash, parsed);
        }

        /// Property 3: Prefix + suffix reconstruction equals full hex
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

        /// Property 5: Algorithm conversions are bijective
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
