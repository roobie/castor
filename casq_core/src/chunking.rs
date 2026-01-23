//! Content-defined chunking using FastCDC.

use crate::error::Result;
use crate::hash::Hash;
use crate::object::ChunkEntry;

/// Configuration for the chunker.
#[derive(Debug, Clone)]
pub struct ChunkerConfig {
    /// Minimum chunk size in bytes.
    pub min_size: usize,
    /// Average (target) chunk size in bytes.
    pub avg_size: usize,
    /// Maximum chunk size in bytes.
    pub max_size: usize,
}

impl Default for ChunkerConfig {
    fn default() -> Self {
        Self {
            min_size: 256 * 1024,  // 256 KB
            avg_size: 512 * 1024,  // 512 KB
            max_size: 1024 * 1024, // 1 MB
        }
    }
}

/// Chunk a file into content-defined chunks using FastCDC.
///
/// Returns a list of chunk entries with hashes and sizes.
pub fn chunk_file(data: &[u8], config: &ChunkerConfig) -> Result<Vec<ChunkEntry>> {
    use fastcdc::ronomon::FastCDC;

    let chunker = FastCDC::new(data, config.min_size, config.avg_size, config.max_size);

    let mut chunks = Vec::new();
    for chunk in chunker {
        let chunk_data = &data[chunk.offset..chunk.offset + chunk.length];
        let hash = Hash::hash_bytes(chunk_data);
        chunks.push(ChunkEntry {
            hash,
            size: chunk.length as u64,
        });
    }

    Ok(chunks)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chunk_file_basic() {
        // Create a 2MB file
        let data = vec![0u8; 2 * 1024 * 1024];
        let config = ChunkerConfig::default();

        let chunks = chunk_file(&data, &config).unwrap();

        // Should have at least 2 chunks (2MB with ~512KB average)
        assert!(
            chunks.len() >= 2,
            "Expected at least 2 chunks, got {}",
            chunks.len()
        );

        // Verify total size matches
        let total_size: u64 = chunks.iter().map(|c| c.size).sum();
        assert_eq!(total_size, data.len() as u64);

        // Verify each chunk is within bounds
        for chunk in &chunks {
            assert!(
                chunk.size >= config.min_size as u64,
                "Chunk size {} is below minimum {}",
                chunk.size,
                config.min_size
            );
            assert!(
                chunk.size <= config.max_size as u64,
                "Chunk size {} exceeds maximum {}",
                chunk.size,
                config.max_size
            );
        }
    }

    #[test]
    fn test_chunk_boundaries() {
        // Test with different data patterns
        let data = (0..2 * 1024 * 1024)
            .map(|i| (i % 256) as u8)
            .collect::<Vec<_>>();
        let config = ChunkerConfig::default();

        let chunks = chunk_file(&data, &config).unwrap();

        // Verify chunk size constraints
        for chunk in &chunks {
            assert!(
                chunk.size >= config.min_size as u64 || chunk.size == data.len() as u64, // Last chunk may be smaller
                "Chunk size {} violates min size {}",
                chunk.size,
                config.min_size
            );
            assert!(
                chunk.size <= config.max_size as u64,
                "Chunk size {} exceeds max size {}",
                chunk.size,
                config.max_size
            );
        }
    }

    #[test]
    fn test_deterministic() {
        // Same data should produce same chunks
        let data = vec![42u8; 2 * 1024 * 1024];
        let config = ChunkerConfig::default();

        let chunks1 = chunk_file(&data, &config).unwrap();
        let chunks2 = chunk_file(&data, &config).unwrap();

        assert_eq!(
            chunks1.len(),
            chunks2.len(),
            "Chunk count should be deterministic"
        );

        for (c1, c2) in chunks1.iter().zip(chunks2.iter()) {
            assert_eq!(c1.hash, c2.hash, "Chunk hashes should be deterministic");
            assert_eq!(c1.size, c2.size, "Chunk sizes should be deterministic");
        }
    }

    #[test]
    fn test_small_file() {
        // File smaller than min_size should create a single chunk
        let data = vec![0u8; 100 * 1024]; // 100 KB
        let config = ChunkerConfig::default();

        let chunks = chunk_file(&data, &config).unwrap();

        // Should be a single chunk
        assert_eq!(chunks.len(), 1, "Small file should create single chunk");
        assert_eq!(chunks[0].size, data.len() as u64);
    }

    #[test]
    fn test_empty_file() {
        let data = vec![];
        let config = ChunkerConfig::default();

        let chunks = chunk_file(&data, &config).unwrap();

        // Empty file should create no chunks
        assert_eq!(chunks.len(), 0, "Empty file should create no chunks");
    }
}
