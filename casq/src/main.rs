use anyhow::{Context, Result};
use casq_core::{Algorithm, Hash, Store};
use clap::{Parser, Subcommand};
use std::io;
use std::path::{Path, PathBuf};

mod output;
use output::*;

/// casq - A content-addressed file store
#[derive(Parser)]
#[command(name = "casq")]
#[command(about = "Content-addressed file store using BLAKE3", long_about = None)]
#[command(version)]
struct Cli {
    /// Store root directory (defaults to CASQ_ROOT env var or ./casq-store)
    #[arg(short, long, global = true)]
    root: Option<PathBuf>,

    /// Output results as JSON
    #[arg(long, global = true)]
    json: bool,

    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Initialize a new store
    Init {
        /// Hash algorithm to use
        #[arg(long, default_value = "blake3")]
        algo: String,
    },

    /// Add files or directories to the store
    Add {
        /// Paths to add (or "-" to read from stdin)
        #[arg(required = true)]
        paths: Vec<String>,

        /// Create a reference to the added content
        #[arg(long)]
        ref_name: Option<String>,
    },

    /// Materialize an object to the filesystem
    Materialize {
        /// Hash of the object to materialize
        hash: String,

        /// Destination path
        dest: PathBuf,
    },

    /// Output blob content to stdout
    Cat {
        /// Hash of the blob
        hash: String,
    },

    /// List tree contents or show blob info (lists refs if no hash given)
    Ls {
        /// Hash of the object (lists all refs if omitted)
        hash: Option<String>,

        /// Show detailed information
        #[arg(short, long)]
        long: bool,
    },

    /// Show object metadata
    Stat {
        /// Hash of the object
        hash: String,
    },

    /// Garbage collect unreferenced objects
    Gc {
        /// Dry run - show what would be deleted without deleting
        #[arg(long)]
        dry_run: bool,
    },

    /// Find orphaned tree roots (unreferenced trees)
    Orphans {
        /// Show detailed information
        #[arg(short, long)]
        long: bool,
    },

    /// View operation journal
    Journal {
        /// Show only recent N entries
        #[arg(long)]
        recent: Option<usize>,

        /// Show only orphaned entries
        #[arg(long)]
        orphans: bool,
    },

    /// Manage references
    #[command(subcommand)]
    Refs(RefsCommands),
}

#[derive(Subcommand)]
enum RefsCommands {
    /// Add a reference
    Add {
        /// Reference name
        name: String,

        /// Hash to reference
        hash: String,
    },

    /// List all references
    List,

    /// Remove a reference
    Rm {
        /// Reference name
        name: String,
    },
}

fn main() {
    let cli = Cli::parse();

    // Determine store root: CLI arg > CASTOR_ROOT env var > ./casq-store default
    let root = cli
        .root
        .or_else(|| std::env::var("CASTOR_ROOT").ok().map(PathBuf::from))
        .unwrap_or_else(|| PathBuf::from("./casq-store"));

    // Create output writer
    let output = OutputWriter::new(cli.json);

    // Execute command and handle errors
    let result = match cli.command {
        Commands::Init { algo } => cmd_init(&root, &algo, &output),
        Commands::Add { paths, ref_name } => cmd_add(&root, paths, ref_name, &output),
        Commands::Materialize { hash, dest } => cmd_materialize(&root, &hash, &dest, &output),
        Commands::Cat { hash } => cmd_cat(&root, &hash, &output),
        Commands::Ls { hash, long } => cmd_ls(&root, &hash, long, &output),
        Commands::Stat { hash } => cmd_stat(&root, &hash, &output),
        Commands::Gc { dry_run } => cmd_gc(&root, dry_run, &output),
        Commands::Orphans { long } => cmd_orphans(&root, long, &output),
        Commands::Journal { recent, orphans } => cmd_journal(&root, recent, orphans, &output),
        Commands::Refs(refs_cmd) => match refs_cmd {
            RefsCommands::Add { name, hash } => cmd_refs_add(&root, &name, &hash, &output),
            RefsCommands::List => cmd_refs_list(&root, &output),
            RefsCommands::Rm { name } => cmd_refs_rm(&root, &name, &output),
        },
    };

    // Handle errors and set exit code
    if let Err(e) = result {
        output.write_error(&e, 1);
        std::process::exit(1);
    }
}

fn cmd_init(root: &Path, algo: &str, output: &OutputWriter) -> Result<()> {
    let algorithm = match algo {
        "blake3" => Algorithm::Blake3,
        _ => anyhow::bail!("Unsupported algorithm: {}", algo),
    };

    Store::init(root, algorithm)
        .with_context(|| format!("Failed to initialize store at {}", root.display()))?;

    let data = InitOutput {
        success: true,
        result_code: 0,
        root: root.display().to_string(),
        algorithm: algorithm.as_str().to_string(),
    };

    output.write(&data, || {
        format!(
            "Initialized casq store at {}\nAlgorithm: {}\n",
            root.display(),
            algorithm.as_str()
        )
    })?;

    Ok(())
}

fn cmd_add(
    root: &Path,
    paths: Vec<String>,
    ref_name: Option<String>,
    output: &OutputWriter,
) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    // Detect stdin mode
    let has_stdin = paths.iter().any(|p| p == "-");
    let has_paths = paths.iter().any(|p| p != "-");

    // Validate: no mixing stdin with filesystem paths
    if has_stdin && has_paths {
        anyhow::bail!(
            "Cannot mix stdin ('-') with filesystem paths.\n\
             Use either: casq add - (for stdin) OR casq add path1 path2 (for files)"
        );
    }

    // Validate: at most one stdin reference
    if paths.iter().filter(|p| *p == "-").count() > 1 {
        anyhow::bail!("stdin can only be read once per invocation");
    }

    let mut objects = Vec::new();
    let mut reference = None;

    // Process based on mode
    if has_stdin {
        let hash = add_from_stdin(&store)?;
        objects.push(AddedObject {
            hash,
            path: "(stdin)".to_string(),
        });

        // Create reference if requested
        if let Some(ref name) = ref_name {
            store
                .refs()
                .add(name, &hash)
                .with_context(|| format!("Failed to create reference: {}", name))?;
            reference = Some(ReferenceCreated {
                name: name.clone(),
                hash,
            });
        }
    } else {
        // Regular filesystem paths
        let mut last_hash = None;
        for path_str in paths {
            let path = PathBuf::from(&path_str);
            let hash = store
                .add_path(&path)
                .with_context(|| format!("Failed to add path: {}", path.display()))?;

            objects.push(AddedObject {
                hash,
                path: path.display().to_string(),
            });
            last_hash = Some(hash);
        }

        // Create reference if requested (points to last hash if multiple paths)
        if let Some(ref name) = ref_name
            && let Some(hash) = last_hash
        {
            store
                .refs()
                .add(name, &hash)
                .with_context(|| format!("Failed to create reference: {}", name))?;
            reference = Some(ReferenceCreated {
                name: name.clone(),
                hash,
            });
        }
    }

    let data = AddOutput {
        success: true,
        result_code: 0,
        objects: objects.clone(),
        reference: reference.clone(),
    };

    output.write(&data, || {
        let mut text = String::new();
        for obj in &objects {
            text.push_str(&format!("{} {}\n", obj.hash, obj.path));
        }
        if let Some(ref r) = reference {
            text.push_str(&format!("Created reference: {} -> {}\n", r.name, r.hash));
        }
        text
    })?;

    Ok(())
}

fn add_from_stdin(store: &Store) -> Result<Hash> {
    // Validate stdin is not a TTY (prevent user confusion)
    if atty::is(atty::Stream::Stdin) {
        anyhow::bail!(
            "stdin is a terminal (refusing to read). Pipe data with: command | casq add -"
        );
    }

    let stdin = io::stdin();
    let hash = store
        .add_stdin(stdin.lock())
        .with_context(|| "Failed to read from stdin")?;

    Ok(hash)
}

fn cmd_materialize(root: &Path, hash_str: &str, dest: &Path, output: &OutputWriter) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let hash = Hash::from_hex(hash_str).with_context(|| format!("Invalid hash: {}", hash_str))?;

    store
        .materialize(&hash, dest)
        .with_context(|| format!("Failed to materialize {} to {}", hash, dest.display()))?;

    let data = MaterializeOutput {
        success: true,
        result_code: 0,
        hash,
        destination: dest.display().to_string(),
    };

    output.write(&data, || {
        format!("Materialized {} to {}\n", hash, dest.display())
    })?;

    Ok(())
}

fn cmd_cat(root: &Path, hash_str: &str, output: &OutputWriter) -> Result<()> {
    if output.is_json() {
        anyhow::bail!(
            "The 'cat' command outputs binary data to stdout and cannot be used with --json.\n\
             Alternatives:\n\
             - Use 'materialize' to save to a file\n\
             - Use 'stat' to get metadata\n\
             - Use 'ls' to list tree contents"
        );
    }

    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let hash = Hash::from_hex(hash_str).with_context(|| format!("Invalid hash: {}", hash_str))?;

    let stdout = io::stdout();
    let mut handle = stdout.lock();

    store
        .cat_blob(&hash, &mut handle)
        .with_context(|| format!("Failed to output blob {}", hash))?;

    Ok(())
}

fn cmd_ls(root: &Path, hash_str: &Option<String>, long: bool, output: &OutputWriter) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    // If no hash provided, list all refs
    if hash_str.is_none() {
        let refs = store
            .refs()
            .list()
            .with_context(|| "Failed to list references")?;

        let ref_infos: Vec<RefInfo> = refs
            .into_iter()
            .map(|(name, hash)| RefInfo { name, hash })
            .collect();

        let data = LsOutput {
            success: true,
            result_code: 0,
            data: LsData::RefList {
                refs: ref_infos.clone(),
            },
        };

        output.write(&data, || {
            if ref_infos.is_empty() {
                "No references (use 'casq add --ref-name' to create one)\n".to_string()
            } else {
                let mut text = String::new();
                for r in &ref_infos {
                    if long {
                        // Try to determine type
                        let type_str = if store.get_tree(&r.hash).is_ok() {
                            "tree"
                        } else {
                            "blob"
                        };
                        text.push_str(&format!("{} {} -> {}\n", type_str, r.name, r.hash));
                    } else {
                        text.push_str(&format!("{} -> {}\n", r.name, r.hash));
                    }
                }
                text
            }
        })?;

        return Ok(());
    }

    // Hash was provided - show object contents
    let hash = Hash::from_hex(hash_str.as_ref().unwrap())
        .with_context(|| format!("Invalid hash: {}", hash_str.as_ref().unwrap()))?;

    // Check if it's a tree or blob
    let obj_path = store.object_path(&hash);
    if !obj_path.exists() {
        anyhow::bail!("Object not found: {}", hash);
    }

    // Try to read as tree first
    match store.get_tree(&hash) {
        Ok(entries) => {
            // It's a tree
            let entry_infos: Vec<TreeEntryInfo> = entries
                .iter()
                .map(|e| TreeEntryInfo {
                    name: e.name.clone(),
                    entry_type: match e.entry_type {
                        casq_core::EntryType::Blob => "blob".to_string(),
                        casq_core::EntryType::Tree => "tree".to_string(),
                    },
                    mode: if long {
                        Some(format!("{:06o}", e.mode))
                    } else {
                        None
                    },
                    hash: if long { Some(e.hash) } else { None },
                })
                .collect();

            let data = LsOutput {
                success: true,
                result_code: 0,
                data: LsData::TreeContents {
                    hash,
                    entries: entry_infos.clone(),
                },
            };

            output.write(&data, || {
                let mut text = String::new();
                for entry in &entries {
                    if long {
                        let type_char = match entry.entry_type {
                            casq_core::EntryType::Blob => 'b',
                            casq_core::EntryType::Tree => 't',
                        };
                        text.push_str(&format!(
                            "{} {:06o} {} {}\n",
                            type_char, entry.mode, entry.hash, entry.name
                        ));
                    } else {
                        text.push_str(&format!("{}\n", entry.name));
                    }
                }
                text
            })?;
        }
        Err(_) => {
            // Try as blob
            let blob = store
                .get_blob(&hash)
                .with_context(|| format!("Failed to read object {}", hash))?;

            let data = LsOutput {
                success: true,
                result_code: 0,
                data: LsData::BlobInfo(BlobInfo {
                    hash,
                    size: blob.len() as u64,
                }),
            };

            output.write(&data, || {
                if long {
                    format!("blob {} bytes\n", blob.len())
                } else {
                    "blob\n".to_string()
                }
            })?;
        }
    }

    Ok(())
}

fn cmd_stat(root: &Path, hash_str: &str, output: &OutputWriter) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let hash = Hash::from_hex(hash_str).with_context(|| format!("Invalid hash: {}", hash_str))?;

    let obj_path = store.object_path(&hash);
    if !obj_path.exists() {
        anyhow::bail!("Object not found: {}", hash);
    }

    // Get file metadata
    let metadata =
        std::fs::metadata(&obj_path).with_context(|| "Failed to read object metadata")?;

    // Try to determine type
    match store.get_tree(&hash) {
        Ok(entries) => {
            let data = StatOutput {
                success: true,
                result_code: 0,
                data: StatData::Tree(TreeStatInfo {
                    hash,
                    entry_count: entries.len(),
                    path: obj_path.display().to_string(),
                }),
            };

            output.write(&data, || {
                format!(
                    "Hash: {}\nType: tree\nEntries: {}\nSize: {} bytes (on disk)\nPath: {}\n",
                    hash,
                    entries.len(),
                    metadata.len(),
                    obj_path.display()
                )
            })?;
        }
        Err(_) => {
            // It's a blob
            let blob = store
                .get_blob(&hash)
                .with_context(|| "Failed to read blob")?;

            let data = StatOutput {
                success: true,
                result_code: 0,
                data: StatData::Blob(BlobStatInfo {
                    hash,
                    size: blob.len() as u64,
                    size_on_disk: metadata.len(),
                    path: obj_path.display().to_string(),
                }),
            };

            output.write(&data, || {
                format!(
                    "Hash: {}\nType: blob\nSize: {} bytes\nSize (on disk): {} bytes\nPath: {}\n",
                    hash,
                    blob.len(),
                    metadata.len(),
                    obj_path.display()
                )
            })?;
        }
    }

    Ok(())
}

fn cmd_gc(root: &Path, dry_run: bool, output: &OutputWriter) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let stats = store
        .gc(dry_run)
        .with_context(|| "Failed to run garbage collection")?;

    let data = GcOutput {
        success: true,
        result_code: 0,
        dry_run,
        objects_deleted: stats.objects_deleted,
        bytes_freed: stats.bytes_freed,
    };

    output.write(&data, || {
        if dry_run {
            format!(
                "Dry run - no objects deleted\nWould delete {} objects\nWould free {} bytes\n",
                stats.objects_deleted, stats.bytes_freed
            )
        } else {
            format!(
                "Deleted {} objects\nFreed {} bytes\n",
                stats.objects_deleted, stats.bytes_freed
            )
        }
    })?;

    Ok(())
}

fn cmd_orphans(root: &Path, long: bool, output: &OutputWriter) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let orphans = store
        .find_orphan_roots()
        .with_context(|| "Failed to find orphan roots")?;

    let orphan_infos: Vec<OrphanInfo> = orphans.iter().map(|o| o.clone().into()).collect();

    let data = OrphansOutput {
        success: true,
        result_code: 0,
        orphans: orphan_infos.clone(),
    };

    output.write(&data, || {
        if orphan_infos.is_empty() {
            "No orphaned tree roots found\n".to_string()
        } else {
            let mut text = String::new();
            for orphan in &orphan_infos {
                if long {
                    text.push_str(&format!("Hash: {}\n", orphan.hash));
                    text.push_str("Type: tree\n");
                    text.push_str(&format!("Entries: {}\n", orphan.entry_count));
                    text.push_str(&format!("Approx size: {} bytes\n", orphan.approx_size));
                    text.push_str("---\n");
                } else {
                    text.push_str(&format!(
                        "{}  {} entries\n",
                        orphan.hash, orphan.entry_count
                    ));
                }
            }
            text
        }
    })?;

    Ok(())
}

fn cmd_journal(
    root: &Path,
    recent: Option<usize>,
    orphans: bool,
    output: &OutputWriter,
) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let entries = if orphans {
        // Show only orphaned entries
        store
            .find_orphan_journal_entries()
            .with_context(|| "Failed to find orphaned journal entries")?
    } else if let Some(count) = recent {
        // Show recent N entries
        store
            .journal()
            .read_recent(count)
            .with_context(|| "Failed to read journal entries")?
    } else {
        // Show all entries (default to recent 10 if not specified)
        store
            .journal()
            .read_recent(10)
            .with_context(|| "Failed to read journal entries")?
    };

    let entry_infos: Vec<JournalEntryInfo> = entries
        .iter()
        .map(|e| {
            let datetime = chrono::DateTime::from_timestamp(e.timestamp, 0)
                .unwrap_or_else(|| chrono::DateTime::from_timestamp(0, 0).unwrap());
            let timestamp_human = datetime.format("%Y-%m-%dT%H:%M:%SZ").to_string();

            JournalEntryInfo {
                timestamp: e.timestamp as u64,
                timestamp_human,
                operation: e.operation.clone(),
                hash: e.hash,
                path: e.path.clone(),
                metadata: if e.metadata.is_empty() {
                    None
                } else {
                    Some(e.metadata.clone())
                },
            }
        })
        .collect();

    let data = JournalOutput {
        success: true,
        result_code: 0,
        entries: entry_infos.clone(),
    };

    output.write(&data, || {
        if entry_infos.is_empty() {
            if orphans {
                "No orphaned journal entries found\n".to_string()
            } else {
                "No journal entries\n".to_string()
            }
        } else {
            let mut text = String::new();
            for entry in &entries {
                // Format timestamp as human-readable
                let datetime = chrono::DateTime::from_timestamp(entry.timestamp, 0)
                    .unwrap_or_else(|| chrono::DateTime::from_timestamp(0, 0).unwrap());
                let formatted_time = datetime.format("%Y-%m-%d %H:%M:%S");

                text.push_str(&format!(
                    "{}  {}  {}  {}  {}\n",
                    formatted_time, entry.operation, entry.hash, entry.path, entry.metadata
                ));
            }
            text
        }
    })?;

    Ok(())
}

fn cmd_refs_add(root: &Path, name: &str, hash_str: &str, output: &OutputWriter) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let hash = Hash::from_hex(hash_str).with_context(|| format!("Invalid hash: {}", hash_str))?;

    store
        .refs()
        .add(name, &hash)
        .with_context(|| format!("Failed to add reference: {}", name))?;

    let data = RefsAddOutput {
        success: true,
        result_code: 0,
        name: name.to_string(),
        hash,
    };

    output.write(&data, || format!("{} -> {}\n", name, hash))?;

    Ok(())
}

fn cmd_refs_list(root: &Path, output: &OutputWriter) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let refs = store
        .refs()
        .list()
        .with_context(|| "Failed to list references")?;

    let ref_infos: Vec<RefInfo> = refs
        .into_iter()
        .map(|(name, hash)| RefInfo { name, hash })
        .collect();

    let data = RefsListOutput {
        success: true,
        result_code: 0,
        refs: ref_infos.clone(),
    };

    output.write(&data, || {
        if ref_infos.is_empty() {
            "No references\n".to_string()
        } else {
            let mut text = String::new();
            for r in &ref_infos {
                text.push_str(&format!("{} -> {}\n", r.name, r.hash));
            }
            text
        }
    })?;

    Ok(())
}

fn cmd_refs_rm(root: &Path, name: &str, output: &OutputWriter) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    store
        .refs()
        .remove(name)
        .with_context(|| format!("Failed to remove reference: {}", name))?;

    let data = RefsRmOutput {
        success: true,
        result_code: 0,
        name: name.to_string(),
    };

    output.write(&data, || format!("Removed reference: {}\n", name))?;

    Ok(())
}
