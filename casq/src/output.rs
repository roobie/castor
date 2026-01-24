//! Output formatting for CLI commands.
//!
//! Provides abstraction layer for outputting results in text or JSON format.

use anyhow::Result;
use casq_core::{Hash, OrphanRoot};
use serde::Serialize;
use std::io::{self, Write};

/// Output format selection.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OutputFormat {
    Text,
    Json,
}

/// Writer for command output with format abstraction.
pub struct OutputWriter {
    format: OutputFormat,
    stdout: io::Stdout,
}

impl OutputWriter {
    /// Create a new OutputWriter.
    pub fn new(json: bool) -> Self {
        Self {
            format: if json {
                OutputFormat::Json
            } else {
                OutputFormat::Text
            },
            stdout: io::stdout(),
        }
    }

    /// Check if JSON mode is enabled.
    pub fn is_json(&self) -> bool {
        self.format == OutputFormat::Json
    }

    /// Write output using the configured format.
    ///
    /// The `data` parameter must be a serializable struct that includes
    /// `success: bool` and `result_code: u8` fields.
    ///
    /// The `text_fn` closure is called only in text mode to generate the
    /// human-readable output.
    pub fn write<T: Serialize>(
        &self,
        data: &T,
        text_fn: impl FnOnce() -> String,
    ) -> Result<()> {
        match self.format {
            OutputFormat::Json => {
                let json = serde_json::to_string_pretty(data)?;
                writeln!(&self.stdout, "{}", json)?;
            }
            OutputFormat::Text => {
                let text = text_fn();
                if !text.is_empty() {
                    write!(&self.stdout, "{}", text)?;
                }
            }
        }
        Ok(())
    }

    /// Write an error message to stderr.
    ///
    /// In JSON mode, writes a JSON error object with success=false.
    /// In text mode, writes the error message directly.
    pub fn write_error(&self, error: &anyhow::Error, result_code: u8) {
        match self.format {
            OutputFormat::Json => {
                let error_output = ErrorOutput {
                    success: false,
                    result_code,
                    error: error.to_string(),
                };
                if let Ok(json) = serde_json::to_string_pretty(&error_output) {
                    let _ = writeln!(io::stderr(), "{}", json);
                }
            }
            OutputFormat::Text => {
                let _ = writeln!(io::stderr(), "Error: {}", error);
            }
        }
    }
}

// ============================================================================
// Data Transfer Objects (DTOs) for JSON output
// ============================================================================

/// Error output structure.
#[derive(Debug, Serialize)]
pub struct ErrorOutput {
    pub success: bool,
    pub result_code: u8,
    pub error: String,
}

/// Output for `init` command.
#[derive(Debug, Serialize)]
pub struct InitOutput {
    pub success: bool,
    pub result_code: u8,
    pub root: String,
    pub algorithm: String,
}

/// Object added during `add` command.
#[derive(Debug, Clone, Serialize)]
pub struct AddedObject {
    pub hash: Hash,
    pub path: String,
}

/// Reference created during `add` command.
#[derive(Debug, Clone, Serialize)]
pub struct ReferenceCreated {
    pub name: String,
    pub hash: Hash,
}

/// Output for `add` command.
#[derive(Debug, Serialize)]
pub struct AddOutput {
    pub success: bool,
    pub result_code: u8,
    pub objects: Vec<AddedObject>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reference: Option<ReferenceCreated>,
}

/// Output for `materialize` command.
#[derive(Debug, Serialize)]
pub struct MaterializeOutput {
    pub success: bool,
    pub result_code: u8,
    pub hash: Hash,
    pub destination: String,
}

/// Reference information for `refs list`.
#[derive(Debug, Clone, Serialize)]
pub struct RefInfo {
    pub name: String,
    pub hash: Hash,
}

/// Tree entry information for `ls` command.
#[derive(Debug, Clone, Serialize)]
pub struct TreeEntryInfo {
    pub name: String,
    pub entry_type: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub mode: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hash: Option<Hash>,
}

/// Blob information for `ls` command.
#[derive(Debug, Serialize)]
pub struct BlobInfo {
    pub hash: Hash,
    pub size: u64,
}

/// Data variants for `ls` command.
#[derive(Debug, Serialize)]
#[serde(tag = "type")]
pub enum LsData {
    RefList { refs: Vec<RefInfo> },
    TreeContents { hash: Hash, entries: Vec<TreeEntryInfo> },
    BlobInfo(BlobInfo),
}

/// Output for `ls` command.
#[derive(Debug, Serialize)]
pub struct LsOutput {
    pub success: bool,
    pub result_code: u8,
    #[serde(flatten)]
    pub data: LsData,
}

/// Tree statistics for `stat` command.
#[derive(Debug, Serialize)]
pub struct TreeStatInfo {
    pub hash: Hash,
    pub entry_count: usize,
    pub path: String,
}

/// Blob statistics for `stat` command.
#[derive(Debug, Serialize)]
pub struct BlobStatInfo {
    pub hash: Hash,
    pub size: u64,
    pub size_on_disk: u64,
    pub path: String,
}

/// Data variants for `stat` command.
#[derive(Debug, Serialize)]
#[serde(tag = "type")]
pub enum StatData {
    Tree(TreeStatInfo),
    Blob(BlobStatInfo),
}

/// Output for `stat` command.
#[derive(Debug, Serialize)]
pub struct StatOutput {
    pub success: bool,
    pub result_code: u8,
    #[serde(flatten)]
    pub data: StatData,
}

/// Output for `gc` command.
#[derive(Debug, Serialize)]
pub struct GcOutput {
    pub success: bool,
    pub result_code: u8,
    pub dry_run: bool,
    pub objects_deleted: usize,
    pub bytes_freed: u64,
}

/// Orphan information for `orphans` command.
#[derive(Debug, Clone, Serialize)]
pub struct OrphanInfo {
    pub hash: Hash,
    pub entry_count: usize,
    pub approx_size: u64,
}

impl From<OrphanRoot> for OrphanInfo {
    fn from(root: OrphanRoot) -> Self {
        Self {
            hash: root.hash,
            entry_count: root.entry_count,
            approx_size: root.approx_size,
        }
    }
}

/// Output for `orphans` command.
#[derive(Debug, Serialize)]
pub struct OrphansOutput {
    pub success: bool,
    pub result_code: u8,
    pub orphans: Vec<OrphanInfo>,
}

/// Journal entry information.
#[derive(Debug, Clone, Serialize)]
pub struct JournalEntryInfo {
    pub timestamp: u64,
    pub timestamp_human: String,
    pub operation: String,
    pub hash: Hash,
    pub path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<String>,
}

/// Output for `journal` command.
#[derive(Debug, Serialize)]
pub struct JournalOutput {
    pub success: bool,
    pub result_code: u8,
    pub entries: Vec<JournalEntryInfo>,
}

/// Output for `refs add` command.
#[derive(Debug, Serialize)]
pub struct RefsAddOutput {
    pub success: bool,
    pub result_code: u8,
    pub name: String,
    pub hash: Hash,
}

/// Output for `refs list` command.
#[derive(Debug, Serialize)]
pub struct RefsListOutput {
    pub success: bool,
    pub result_code: u8,
    pub refs: Vec<RefInfo>,
}

/// Output for `refs rm` command.
#[derive(Debug, Serialize)]
pub struct RefsRmOutput {
    pub success: bool,
    pub result_code: u8,
    pub name: String,
}
