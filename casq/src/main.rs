use anyhow::{Context, Result};
use casq_core::{Algorithm, Hash, Store};
use clap::{Parser, Subcommand};
use std::io;
use std::path::{Path, PathBuf};

/// Castor - A content-addressed file store
#[derive(Parser)]
#[command(name = "casq")]
#[command(about = "Content-addressed file store using BLAKE3", long_about = None)]
#[command(version)]
struct Cli {
    /// Store root directory (defaults to CASTOR_ROOT env var or ./casq-store)
    #[arg(short, long, global = true)]
    root: Option<PathBuf>,

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
        /// Paths to add
        #[arg(required = true)]
        paths: Vec<PathBuf>,

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

fn main() -> Result<()> {
    let cli = Cli::parse();

    // Determine store root: CLI arg > CASTOR_ROOT env var > ./casq-store default
    let root = cli
        .root
        .or_else(|| std::env::var("CASTOR_ROOT").ok().map(PathBuf::from))
        .unwrap_or_else(|| PathBuf::from("./casq-store"));

    match cli.command {
        Commands::Init { algo } => cmd_init(&root, &algo),
        Commands::Add { paths, ref_name } => cmd_add(&root, paths, ref_name),
        Commands::Materialize { hash, dest } => cmd_materialize(&root, &hash, &dest),
        Commands::Cat { hash } => cmd_cat(&root, &hash),
        Commands::Ls { hash, long } => cmd_ls(&root, &hash, long),
        Commands::Stat { hash } => cmd_stat(&root, &hash),
        Commands::Gc { dry_run } => cmd_gc(&root, dry_run),
        Commands::Refs(refs_cmd) => match refs_cmd {
            RefsCommands::Add { name, hash } => cmd_refs_add(&root, &name, &hash),
            RefsCommands::List => cmd_refs_list(&root),
            RefsCommands::Rm { name } => cmd_refs_rm(&root, &name),
        },
    }
}

fn cmd_init(root: &Path, algo: &str) -> Result<()> {
    let algorithm = match algo {
        "blake3" => Algorithm::Blake3,
        _ => anyhow::bail!("Unsupported algorithm: {}", algo),
    };

    Store::init(root, algorithm)
        .with_context(|| format!("Failed to initialize store at {}", root.display()))?;

    println!("Initialized casq store at {}", root.display());
    println!("Algorithm: {}", algorithm.as_str());

    Ok(())
}

fn cmd_add(root: &Path, paths: Vec<PathBuf>, ref_name: Option<String>) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    for path in paths {
        let hash = store
            .add_path(&path)
            .with_context(|| format!("Failed to add path: {}", path.display()))?;

        println!("{} {}", hash, path.display());

        // Create reference if requested
        if let Some(ref name) = ref_name {
            store
                .refs()
                .add(name, &hash)
                .with_context(|| format!("Failed to create reference: {}", name))?;
            println!("Created reference: {} -> {}", name, hash);
        }
    }

    Ok(())
}

fn cmd_materialize(root: &Path, hash_str: &str, dest: &Path) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let hash = Hash::from_hex(hash_str).with_context(|| format!("Invalid hash: {}", hash_str))?;

    store
        .materialize(&hash, dest)
        .with_context(|| format!("Failed to materialize {} to {}", hash, dest.display()))?;

    println!("Materialized {} to {}", hash, dest.display());

    Ok(())
}

fn cmd_cat(root: &Path, hash_str: &str) -> Result<()> {
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

fn cmd_ls(root: &Path, hash_str: &Option<String>, long: bool) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    // If no hash provided, list all refs
    if hash_str.is_none() {
        let refs = store
            .refs()
            .list()
            .with_context(|| "Failed to list references")?;

        if refs.is_empty() {
            println!("No references (use 'casq add --ref-name' to create one)");
        } else {
            for (name, hash) in refs {
                if long {
                    // Try to determine type
                    let type_str = if store.get_tree(&hash).is_ok() {
                        "tree"
                    } else {
                        "blob"
                    };
                    println!("{} {} -> {}", type_str, name, hash);
                } else {
                    println!("{} -> {}", name, hash);
                }
            }
        }
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
            for entry in entries {
                if long {
                    let type_char = match entry.entry_type {
                        casq_core::EntryType::Blob => 'b',
                        casq_core::EntryType::Tree => 't',
                    };
                    println!(
                        "{} {:06o} {} {}",
                        type_char, entry.mode, entry.hash, entry.name
                    );
                } else {
                    println!("{}", entry.name);
                }
            }
        }
        Err(_) => {
            // Try as blob
            let blob = store
                .get_blob(&hash)
                .with_context(|| format!("Failed to read object {}", hash))?;

            if long {
                println!("blob {} bytes", blob.len());
            } else {
                println!("blob");
            }
        }
    }

    Ok(())
}

fn cmd_stat(root: &Path, hash_str: &str) -> Result<()> {
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
            println!("Hash: {}", hash);
            println!("Type: tree");
            println!("Entries: {}", entries.len());
            println!("Size: {} bytes (on disk)", metadata.len());
            println!("Path: {}", obj_path.display());
        }
        Err(_) => {
            // It's a blob
            let blob = store
                .get_blob(&hash)
                .with_context(|| "Failed to read blob")?;

            println!("Hash: {}", hash);
            println!("Type: blob");
            println!("Size: {} bytes", blob.len());
            println!("Size (on disk): {} bytes", metadata.len());
            println!("Path: {}", obj_path.display());
        }
    }

    Ok(())
}

fn cmd_gc(root: &Path, dry_run: bool) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let stats = store
        .gc(dry_run)
        .with_context(|| "Failed to run garbage collection")?;

    if dry_run {
        println!("Dry run - no objects deleted");
        println!("Would delete {} objects", stats.objects_deleted);
        println!("Would free {} bytes", stats.bytes_freed);
    } else {
        println!("Deleted {} objects", stats.objects_deleted);
        println!("Freed {} bytes", stats.bytes_freed);
    }

    Ok(())
}

fn cmd_refs_add(root: &Path, name: &str, hash_str: &str) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let hash = Hash::from_hex(hash_str).with_context(|| format!("Invalid hash: {}", hash_str))?;

    store
        .refs()
        .add(name, &hash)
        .with_context(|| format!("Failed to add reference: {}", name))?;

    println!("{} -> {}", name, hash);

    Ok(())
}

fn cmd_refs_list(root: &Path) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    let refs = store
        .refs()
        .list()
        .with_context(|| "Failed to list references")?;

    if refs.is_empty() {
        println!("No references");
    } else {
        for (name, hash) in refs {
            println!("{} -> {}", name, hash);
        }
    }

    Ok(())
}

fn cmd_refs_rm(root: &Path, name: &str) -> Result<()> {
    let store =
        Store::open(root).with_context(|| format!("Failed to open store at {}", root.display()))?;

    store
        .refs()
        .remove(name)
        .with_context(|| format!("Failed to remove reference: {}", name))?;

    println!("Removed reference: {}", name);

    Ok(())
}
