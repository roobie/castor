//! Binary object format and encoding.
//!
//! Objects are stored with a 16-byte header followed by the payload:
//!
//! ```text
//! 0x00  4   "CAFS" magic
//! 0x04  1   version (u8)
//! 0x05  1   type: 1=blob, 2=tree
//! 0x06  1   algo: 1=blake3-256
//! 0x07  1   reserved (must be 0)
//! 0x08  8   payload_len (u64 LE)
//! 0x10  ... payload
//! ```

use crate::error::{Error, Result};
use crate::hash::Algorithm;

/// Magic bytes at the start of every object file.
pub const MAGIC: &[u8; 4] = b"CAFS";

/// Current object format version.
pub const VERSION: u8 = 1;

/// Size of the object header in bytes.
pub const HEADER_SIZE: usize = 16;

/// Object types.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ObjectType {
    /// A blob (file content).
    Blob = 1,
    /// A tree (directory structure).
    Tree = 2,
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
        }
    }
}

/// A 16-byte object header.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ObjectHeader {
    /// Object format version.
    pub version: u8,
    /// Object type (blob or tree).
    pub object_type: ObjectType,
    /// Hash algorithm used.
    pub algorithm: Algorithm,
    /// Length of the payload in bytes.
    pub payload_len: u64,
}

impl ObjectHeader {
    /// Create a new object header.
    pub fn new(object_type: ObjectType, algorithm: Algorithm, payload_len: u64) -> Self {
        Self {
            version: VERSION,
            object_type,
            algorithm,
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

        // Reserved (1 byte) - already 0

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
        if version != VERSION {
            return Err(Error::invalid_hash(format!(
                "Unsupported version: {} (expected {})",
                version, VERSION
            )));
        }

        // Parse type
        let object_type = ObjectType::from_u8(buf[5])?;

        // Parse algorithm
        let algorithm = Algorithm::from_id(buf[6])?;

        // Check reserved byte
        if buf[7] != 0 {
            return Err(Error::invalid_hash(format!(
                "Reserved byte must be 0, got {}",
                buf[7]
            )));
        }

        // Parse payload length
        let mut len_bytes = [0u8; 8];
        len_bytes.copy_from_slice(&buf[8..16]);
        let payload_len = u64::from_le_bytes(len_bytes);

        Ok(Self {
            version,
            object_type,
            algorithm,
            payload_len,
        })
    }

    /// Validate the header.
    pub fn validate(&self) -> Result<()> {
        if self.version != VERSION {
            return Err(Error::invalid_hash(format!(
                "Unsupported version: {}",
                self.version
            )));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_object_type_conversions() {
        assert_eq!(ObjectType::Blob.to_u8(), 1);
        assert_eq!(ObjectType::Tree.to_u8(), 2);

        assert_eq!(ObjectType::from_u8(1).unwrap(), ObjectType::Blob);
        assert_eq!(ObjectType::from_u8(2).unwrap(), ObjectType::Tree);

        assert!(ObjectType::from_u8(0).is_err());
        assert!(ObjectType::from_u8(3).is_err());
    }

    #[test]
    fn test_header_encode_decode_blob() {
        let header = ObjectHeader::new(ObjectType::Blob, Algorithm::Blake3, 1024);
        let encoded = header.encode();

        assert_eq!(encoded.len(), HEADER_SIZE);
        assert_eq!(&encoded[0..4], MAGIC);

        let decoded = ObjectHeader::decode(&encoded).unwrap();
        assert_eq!(decoded, header);
    }

    #[test]
    fn test_header_encode_decode_tree() {
        let header = ObjectHeader::new(ObjectType::Tree, Algorithm::Blake3, 512);
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
        buf[4] = 99; // Invalid version
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
    fn test_header_decode_reserved_nonzero() {
        let mut buf = [0u8; HEADER_SIZE];
        buf[0..4].copy_from_slice(MAGIC);
        buf[4] = VERSION;
        buf[5] = ObjectType::Blob.to_u8();
        buf[6] = Algorithm::Blake3.id();
        buf[7] = 1; // Reserved byte should be 0

        assert!(ObjectHeader::decode(&buf).is_err());
    }

    #[test]
    fn test_header_payload_len() {
        let header = ObjectHeader::new(ObjectType::Blob, Algorithm::Blake3, 0x123456789ABCDEF0);
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
        let header = ObjectHeader::new(ObjectType::Blob, Algorithm::Blake3, 100);
        assert!(header.validate().is_ok());
    }
}
