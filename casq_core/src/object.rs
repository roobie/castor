//! Binary object format and encoding.
//!
//! Objects are stored with a 16-byte header followed by the payload:
//!
//! Version 1 (legacy):
//! ```text
//! 0x00  4   "CAFS" magic
//! 0x04  1   version (u8) = 1
//! 0x05  1   type: 1=blob, 2=tree
//! 0x06  1   algo: 1=blake3-256
//! 0x07  1   reserved (must be 0)
//! 0x08  8   payload_len (u64 LE)
//! 0x10  ... payload
//! ```
//!
//! Version 2 (current):
//! ```text
//! 0x00  4   "CAFS" magic
//! 0x04  1   version (u8) = 2
//! 0x05  1   type: 1=blob, 2=tree, 3=chunk_list
//! 0x06  1   algo: 1=blake3-256
//! 0x07  1   compression: 0=none, 1=zstd
//! 0x08  8   payload_len (u64 LE) - compressed size
//! 0x10  ... payload
//! ```

use crate::error::{Error, Result};
use crate::hash::Algorithm;

/// Magic bytes at the start of every object file.
pub const MAGIC: &[u8; 4] = b"CAFS";

/// Current object format version.
pub const VERSION: u8 = 2;

/// Size of the object header in bytes.
pub const HEADER_SIZE: usize = 16;

/// Object types.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ObjectType {
    /// A blob (file content).
    Blob = 1,
    /// A tree (directory structure).
    Tree = 2,
    /// A chunk list (for large files split into chunks).
    ChunkList = 3,
}

impl ObjectType {
    /// Convert to byte representation.
    pub fn to_u8(self) -> u8 {
        self as u8
    }

    /// Parse from byte representation.
    pub fn from_u8(value: u8) -> Result<Self> {
        match value {
            1 => Ok(ObjectType::Blob),
            2 => Ok(ObjectType::Tree),
            3 => Ok(ObjectType::ChunkList),
            _ => Err(Error::invalid_hash(format!(
                "Invalid object type: {}",
                value
            ))),
        }
    }

    /// Get the string name of this object type.
    pub fn as_str(&self) -> &'static str {
        match self {
            ObjectType::Blob => "blob",
            ObjectType::Tree => "tree",
            ObjectType::ChunkList => "chunk_list",
        }
    }
}

/// Compression types.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CompressionType {
    /// No compression.
    None = 0,
    /// Zstandard compression.
    Zstd = 1,
}

impl CompressionType {
    /// Convert to byte representation.
    pub fn to_u8(self) -> u8 {
        self as u8
    }

    /// Parse from byte representation.
    pub fn from_u8(value: u8) -> Result<Self> {
        match value {
            0 => Ok(CompressionType::None),
            1 => Ok(CompressionType::Zstd),
            _ => Err(Error::invalid_hash(format!(
                "Invalid compression type: {}",
                value
            ))),
        }
    }

    /// Get the string name of this compression type.
    pub fn as_str(&self) -> &'static str {
        match self {
            CompressionType::None => "none",
            CompressionType::Zstd => "zstd",
        }
    }
}

/// A 16-byte object header.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ObjectHeader {
    /// Object format version.
    pub version: u8,
    /// Object type (blob, tree, or chunk_list).
    pub object_type: ObjectType,
    /// Hash algorithm used.
    pub algorithm: Algorithm,
    /// Compression type (v2+ only).
    pub compression: CompressionType,
    /// Length of the payload in bytes (compressed size if compressed).
    pub payload_len: u64,
}

impl ObjectHeader {
    /// Create a new object header.
    pub fn new(
        object_type: ObjectType,
        algorithm: Algorithm,
        compression: CompressionType,
        payload_len: u64,
    ) -> Self {
        Self {
            version: VERSION,
            object_type,
            algorithm,
            compression,
            payload_len,
        }
    }

    /// Encode the header to a 16-byte array.
    pub fn encode(&self) -> [u8; HEADER_SIZE] {
        let mut buf = [0u8; HEADER_SIZE];

        // Magic (4 bytes)
        buf[0..4].copy_from_slice(MAGIC);

        // Version (1 byte)
        buf[4] = self.version;

        // Type (1 byte)
        buf[5] = self.object_type.to_u8();

        // Algorithm (1 byte)
        buf[6] = self.algorithm.id();

        // Compression (1 byte) - for v2+, or reserved=0 for v1
        buf[7] = self.compression.to_u8();

        // Payload length (8 bytes, little-endian)
        buf[8..16].copy_from_slice(&self.payload_len.to_le_bytes());

        buf
    }

    /// Decode a header from a 16-byte array.
    pub fn decode(buf: &[u8]) -> Result<Self> {
        if buf.len() < HEADER_SIZE {
            return Err(Error::invalid_hash(format!(
                "Header too short: {} bytes (expected {})",
                buf.len(),
                HEADER_SIZE
            )));
        }

        // Check magic
        if &buf[0..4] != MAGIC {
            return Err(Error::invalid_hash(format!(
                "Invalid magic: expected {:?}, got {:?}",
                MAGIC,
                &buf[0..4]
            )));
        }

        // Parse version
        let version = buf[4];
        if version != 1 && version != 2 {
            return Err(Error::invalid_hash(format!(
                "Unsupported version: {} (expected 1 or 2)",
                version
            )));
        }

        // Parse type
        let object_type = ObjectType::from_u8(buf[5])?;

        // Parse algorithm
        let algorithm = Algorithm::from_id(buf[6])?;

        // Parse compression byte (v2) or check reserved byte (v1)
        let compression = if version == 2 {
            CompressionType::from_u8(buf[7])?
        } else {
            // v1: reserved byte must be 0
            if buf[7] != 0 {
                return Err(Error::invalid_hash(format!(
                    "Reserved byte must be 0 for v1, got {}",
                    buf[7]
                )));
            }
            CompressionType::None
        };

        // Parse payload length
        let mut len_bytes = [0u8; 8];
        len_bytes.copy_from_slice(&buf[8..16]);
        let payload_len = u64::from_le_bytes(len_bytes);

        Ok(Self {
            version,
            object_type,
            algorithm,
            compression,
            payload_len,
        })
    }

    /// Validate the header.
    pub fn validate(&self) -> Result<()> {
        if self.version != 1 && self.version != 2 {
            return Err(Error::invalid_hash(format!(
                "Unsupported version: {}",
                self.version
            )));
        }
        Ok(())
    }
}

/// A chunk entry in a ChunkList object.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChunkEntry {
    /// Hash of the chunk content.
    pub hash: crate::hash::Hash,
    /// Size of the chunk in bytes.
    pub size: u64,
}

/// Size of a chunk entry in bytes (32-byte hash + 8-byte size).
pub const CHUNK_ENTRY_SIZE: usize = 40;

/// A chunk list object that references multiple chunks.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChunkList {
    /// List of chunk entries.
    pub chunks: Vec<ChunkEntry>,
}

impl ChunkList {
    /// Encode the chunk list to bytes.
    /// Each entry is 40 bytes: 32-byte hash + 8-byte size (u64 LE).
    pub fn encode(&self) -> Vec<u8> {
        let mut buf = Vec::with_capacity(self.chunks.len() * CHUNK_ENTRY_SIZE);
        for chunk in &self.chunks {
            buf.extend_from_slice(chunk.hash.as_bytes());
            buf.extend_from_slice(&chunk.size.to_le_bytes());
        }
        buf
    }

    /// Decode a chunk list from bytes.
    pub fn decode(bytes: &[u8]) -> Result<Self> {
        if !bytes.len().is_multiple_of(CHUNK_ENTRY_SIZE) {
            return Err(Error::invalid_chunk_list(format!(
                "ChunkList payload size {} is not a multiple of {}",
                bytes.len(),
                CHUNK_ENTRY_SIZE
            )));
        }

        let mut chunks = Vec::new();
        for chunk_bytes in bytes.chunks_exact(CHUNK_ENTRY_SIZE) {
            // Convert slice to array for hash
            let hash_bytes: [u8; 32] = chunk_bytes[0..32]
                .try_into()
                .map_err(|_| Error::invalid_chunk_list("Failed to parse chunk hash"))?;
            let hash = crate::hash::Hash::from_bytes(hash_bytes);

            let size = u64::from_le_bytes(
                chunk_bytes[32..40]
                    .try_into()
                    .map_err(|_| Error::invalid_chunk_list("Failed to parse chunk size"))?,
            );
            chunks.push(ChunkEntry { hash, size });
        }

        Ok(ChunkList { chunks })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_object_type_conversions() {
        assert_eq!(ObjectType::Blob.to_u8(), 1);
        assert_eq!(ObjectType::Tree.to_u8(), 2);
        assert_eq!(ObjectType::ChunkList.to_u8(), 3);

        assert_eq!(ObjectType::from_u8(1).unwrap(), ObjectType::Blob);
        assert_eq!(ObjectType::from_u8(2).unwrap(), ObjectType::Tree);
        assert_eq!(ObjectType::from_u8(3).unwrap(), ObjectType::ChunkList);

        assert!(ObjectType::from_u8(0).is_err());
        assert!(ObjectType::from_u8(4).is_err());
    }

    #[test]
    fn test_header_encode_decode_blob() {
        let header = ObjectHeader::new(
            ObjectType::Blob,
            Algorithm::Blake3,
            CompressionType::None,
            1024,
        );
        let encoded = header.encode();

        assert_eq!(encoded.len(), HEADER_SIZE);
        assert_eq!(&encoded[0..4], MAGIC);

        let decoded = ObjectHeader::decode(&encoded).unwrap();
        assert_eq!(decoded, header);
    }

    #[test]
    fn test_header_encode_decode_tree() {
        let header = ObjectHeader::new(
            ObjectType::Tree,
            Algorithm::Blake3,
            CompressionType::None,
            512,
        );
        let encoded = header.encode();
        let decoded = ObjectHeader::decode(&encoded).unwrap();
        assert_eq!(decoded, header);
    }

    #[test]
    fn test_header_decode_invalid_magic() {
        let mut buf = [0u8; HEADER_SIZE];
        buf[0..4].copy_from_slice(b"XXXX");
        buf[4] = VERSION;
        buf[5] = ObjectType::Blob.to_u8();
        buf[6] = Algorithm::Blake3.id();

        assert!(ObjectHeader::decode(&buf).is_err());
    }

    #[test]
    fn test_header_decode_invalid_version() {
        let mut buf = [0u8; HEADER_SIZE];
        buf[0..4].copy_from_slice(MAGIC);
        buf[4] = 99; // Invalid version (only 1 and 2 are supported)
        buf[5] = ObjectType::Blob.to_u8();
        buf[6] = Algorithm::Blake3.id();

        assert!(ObjectHeader::decode(&buf).is_err());
    }

    #[test]
    fn test_header_decode_invalid_type() {
        let mut buf = [0u8; HEADER_SIZE];
        buf[0..4].copy_from_slice(MAGIC);
        buf[4] = VERSION;
        buf[5] = 99; // Invalid type
        buf[6] = Algorithm::Blake3.id();

        assert!(ObjectHeader::decode(&buf).is_err());
    }

    #[test]
    fn test_header_decode_v1_reserved_nonzero() {
        // v1 format: reserved byte must be 0
        let mut buf = [0u8; HEADER_SIZE];
        buf[0..4].copy_from_slice(MAGIC);
        buf[4] = 1; // v1
        buf[5] = ObjectType::Blob.to_u8();
        buf[6] = Algorithm::Blake3.id();
        buf[7] = 1; // Reserved byte should be 0 in v1

        assert!(ObjectHeader::decode(&buf).is_err());
    }

    #[test]
    fn test_header_decode_v2_compression() {
        // v2 format: compression byte can be non-zero
        let mut buf = [0u8; HEADER_SIZE];
        buf[0..4].copy_from_slice(MAGIC);
        buf[4] = 2; // v2
        buf[5] = ObjectType::Blob.to_u8();
        buf[6] = Algorithm::Blake3.id();
        buf[7] = 1; // CompressionType::Zstd

        let header = ObjectHeader::decode(&buf).unwrap();
        assert_eq!(header.version, 2);
        assert_eq!(header.compression, CompressionType::Zstd);
    }

    #[test]
    fn test_header_decode_invalid_compression() {
        // Invalid compression type should fail
        let mut buf = [0u8; HEADER_SIZE];
        buf[0..4].copy_from_slice(MAGIC);
        buf[4] = 2; // v2
        buf[5] = ObjectType::Blob.to_u8();
        buf[6] = Algorithm::Blake3.id();
        buf[7] = 99; // Invalid compression type

        assert!(ObjectHeader::decode(&buf).is_err());
    }

    #[test]
    fn test_header_payload_len() {
        let header = ObjectHeader::new(
            ObjectType::Blob,
            Algorithm::Blake3,
            CompressionType::None,
            0x123456789ABCDEF0,
        );
        let encoded = header.encode();
        let decoded = ObjectHeader::decode(&encoded).unwrap();
        assert_eq!(decoded.payload_len, 0x123456789ABCDEF0);
    }

    #[test]
    fn test_header_too_short() {
        let buf = [0u8; 10]; // Too short
        assert!(ObjectHeader::decode(&buf).is_err());
    }

    #[test]
    fn test_header_validate() {
        let header = ObjectHeader::new(
            ObjectType::Blob,
            Algorithm::Blake3,
            CompressionType::None,
            100,
        );
        assert!(header.validate().is_ok());
    }

    // Property-based tests
    use proptest::prelude::*;

    // Strategy for generating arbitrary ObjectHeaders
    fn arb_object_header() -> impl Strategy<Value = ObjectHeader> {
        (
            prop::sample::select(vec![ObjectType::Blob, ObjectType::Tree, ObjectType::ChunkList]),
            prop::sample::select(vec![Algorithm::Blake3]),
            prop::sample::select(vec![CompressionType::None, CompressionType::Zstd]),
            any::<u64>(),
        )
            .prop_map(|(object_type, algorithm, compression, payload_len)| {
                ObjectHeader::new(object_type, algorithm, compression, payload_len)
            })
    }

    // Strategy for generating arbitrary ChunkLists
    fn arb_chunk_list() -> impl Strategy<Value = ChunkList> {
        prop::collection::vec(
            (prop::array::uniform32(any::<u8>()), any::<u64>()),
            0..20,
        )
        .prop_map(|chunks| ChunkList {
            chunks: chunks
                .into_iter()
                .map(|(hash_bytes, size)| ChunkEntry {
                    hash: crate::hash::Hash::from_bytes(hash_bytes),
                    size,
                })
                .collect(),
        })
    }

    proptest! {
        #![proptest_config(ProptestConfig {
            cases: 256,
            max_shrink_iters: 10000,
            ..ProptestConfig::default()
        })]

        /// Property 6: Header serialization round-trip
        #[test]
        fn prop_header_roundtrip(header in arb_object_header()) {
            let encoded = header.encode();
            prop_assert_eq!(encoded.len(), HEADER_SIZE);
            let decoded = ObjectHeader::decode(&encoded)?;
            prop_assert_eq!(decoded, header);
        }

        /// Property 7: ChunkList round-trip
        #[test]
        fn prop_chunk_list_roundtrip(chunk_list in arb_chunk_list()) {
            let encoded = chunk_list.encode();
            prop_assert!(encoded.len().is_multiple_of(CHUNK_ENTRY_SIZE));
            let decoded = ChunkList::decode(&encoded)?;
            prop_assert_eq!(decoded, chunk_list);
        }

        /// Property 8: Invalid chunk list sizes rejected
        #[test]
        fn prop_invalid_chunk_size_rejected(
            // Generate byte lengths that are NOT multiples of 40
            bad_len in (1usize..400).prop_filter("not multiple of 40", |n| !n.is_multiple_of(CHUNK_ENTRY_SIZE))
        ) {
            let bad_bytes = vec![0u8; bad_len];
            prop_assert!(ChunkList::decode(&bad_bytes).is_err());
        }

        /// Property 9: ObjectType conversions are bijective
        #[test]
        fn prop_object_type_roundtrip(
            obj_type in prop::sample::select(vec![
                ObjectType::Blob,
                ObjectType::Tree,
                ObjectType::ChunkList,
            ])
        ) {
            let byte = obj_type.to_u8();
            prop_assert_eq!(ObjectType::from_u8(byte)?, obj_type);
        }
    }
}
