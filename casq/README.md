casq — CLI for the casq content-addressed store
=================================================

## Overview
casq is the command-line interface for a small, local-only content-addressed file store. It stores files and directories as immutable objects addressed by their cryptographic hash (BLAKE3 by default), can reconstruct trees, list contents, and garbage-collect unreferenced data.

## Status
Alpha — useful for local single-user workflows. JSON output and strict stdout/stderr separation are supported for scripting.

## Key features
- Content-addressed storage using BLAKE3-256.
- Three object types: blob (file), tree (directory), and chunk-list (for large files in casq_core).
- Store layout: $STORE_ROOT/{config,objects,refs,journal}.
- Refs as named text files under refs/; GC computes reachability from refs.
- --json support for machine-readable output; informational messages/errors go to stderr in JSON mode.

## Quick install & development
This repository uses mise for task automation. Common tasks:

- list tasks: mise tasks
- fetch deps: mise run deps
- build: mise run build
- test: mise run test

You can also use cargo directly for local development:
- Build the CLI: cargo build -p casq
- Run the CLI: cargo run -p casq -- <COMMAND>

## Usage
General form: casq [OPTIONS] <COMMAND>

## Commands
- initialize       Initialize a new store
- put              Put files or directories into the store
- materialize      Materialize an object to the filesystem
- get              Output blob content to stdout
- list             List tree children
- metadata         Show object metadata
- collect-garbage  Garbage collect unreferenced objects
- find-orphans     Find orphaned objects (unreferenced trees and blobs)
- references       Manage named references (add/list/rm)
- help             Show help for commands

## Global options
- -R, --root <ROOT>  Store root directory (defaults to CASQ_ROOT env var or ./casq-store)
- --json             Output results as JSON
- -h, --help         Print help
- -V, --version      Print version

## Examples
- Initialize a new store:
  casq initialize --root ./casq-store

- Add a directory and print the root hash:
  casq put path/to/dir

- Materialize a tree to the filesystem:
  casq materialize <HASH> ./restore-dir

- Stream a blob to stdout:
  casq get <HASH> > file.bin

- List a tree's contents:
  casq list <HASH>

## Notes & conventions
- Object files are named by the hex-encoded hash and stored under objects/<algo>/<first2>/<rest>.
- Tree entries are canonicalized (sorted by name) to ensure stable tree hashes.
- When using --json: only JSON is written to stdout; informational messages and errors go to stderr.

## Contributing
See the repository README for contribution guidelines. Before making changes that affect structure, API, or behavior, update relevant documentation files (CLAUDE.md and top-level READMEs) as appropriate.

## License
> Apache-2.0
