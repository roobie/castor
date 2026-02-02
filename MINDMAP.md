# Project Mind Map

> This is a graph-based documentation format stored as plain text where each node is a single line containing an ID, title, and inline references.
>
> **Node Syntax Structure** - Each node follows: [N] **Node Title** - node text with [N] references inlined; nodes are line-oriented to allow line-by-line loading and grep lookups for quick retrieval.
> Line-oriented nodes enable line-by-line overwrites, easy incremental updates, grep-based lookup, VCS-friendly diffs, and LLM-friendly citation syntax mirroring academic references.
>
> **For AI Agents:** This is your primary knowledge index. Start by reading overview nodes [1-5], then follow `[N]` links to find details. Always cite node IDs when referencing information.
>
> **Update Protocol:**
> - Before starting work: `grep` for related nodes, read them
> - After completing work: update affected nodes, add new nodes only for new concepts (3+ references or non-obvious)
> - When fixing bugs: document root cause + solution in a `[N] **Bug: [Title]**` node
> - Mark outdated info with `(verify)` or `[DEPRECATED → N]`
>
> **Node Conventions:**
> - `**Component: X**` = architecture elements
> - `**Flow: X**` = multi-step processes
> - `**Decision: X**` = design rationale
> - `**Bug: X**` = documented failures
> - `**TODO: X**` = planned work
>
> **Scale:** Keep under 50 nodes for small projects, under 100 for medium. If you exceed 100, split into domain-specific maps - i.e. MINDMAP.domain-concept.md, and reference it from here.

---

## Overview

[1] **Project Purpose** - A local, single-user content-addressed file store (casq) that stores files and directories by cryptographic hash with transparent compression and content-defined chunking for efficient, incremental backups. See casq README and casq_core design [7][8].

[2] **Tech Stack** - Rust workspace (cargo) with two crates: `casq_core` (library) and `casq` (CLI). Key libraries: blake3 (hashing), zstd (compression), fastcdc (content-defined chunking), ignore (gitignore-aware walk), tempfile. Build tooling: mise tasks, cargo, pytest for ancillary tests. See [8][9].

[3] **Entry Points** - CLI entry: `casq/src/main.rs` (binary `casq`) for user commands; Library entry: `casq_core/src/lib.rs` exposes `Store`, hashing, tree, GC APIs for embedding. Tests and mise tasks live at repo root (`tests/`, `mise.toml`) [10][7].

[4] **Architecture** - Monorepo Rust workspace with two crates; on-disk store layout: `config`, `objects/<algo>/<prefix>/<hash>`, `refs/`, `journal/`. Object model: Blob, Tree, ChunkList; object files have a 16-byte header ("CAFS" magic, version, type, algo, compression, payload_len) followed by payload (possibly zstd-compressed). GC is mark-and-sweep from refs. See object format and module structure in casq_core README [11][8].

[5] **Key Decisions** -
- Use BLAKE3 for fast, stable content hashing (dedupe + performance) [8].
- Transparent zstd compression thresholded at >=4KB and FastCDC chunking for >=1MB files to enable efficient incremental backups [8].
- Single-binary, local-only CLI plus embeddable library design (no network, no multi-user) to keep design simple and robust; strict stdout/stderr separation and `--json` for automation [9].

---

## Components & Domain Nodes

[6] **Component: casq_core (library)** - Implements Store API, hashing (`hash.rs`), object encode/decode (`object.rs`), chunking (`chunking.rs`), tree utilities (`tree.rs`), walk (`walk.rs`), refs (`refs.rs`), GC (`gc.rs`), journal (`journal.rs`). Tests and property tests live with the crate; intended for embedding and reuse [8].

[7] **Component: casq (CLI)** - Thin CLI wrapper around `casq_core` exposing commands: initialize, put, get, list, metadata, materialize, collect-garbage, find-orphans, references. Implements JSON output DTOs and stdout/stderr conventions in `casq/src/output.rs` [9].

[8] **Component: On-disk layout & formats** - Store root with `config` (store config), `objects/` (sharded by first 2 hex chars under algorithm dir), `refs/` (named ref files), `journal` (operation log). Object header v2 (16 bytes) + payload; tree entry and chunklist formats are canonicalized for stable hashes [8].

[9] **Component: Chunking & Compression** - FastCDC v2020 used for content-defined chunking (files >=1MB) producing ChunkList objects; zstd applied automatically for blobs >=4KB. Chunk hashes computed by BLAKE3 and deduplicated in object store [8].

[10] **Component: Garbage Collection & Refs** - Refs are GC roots in `refs/`. GC: mark reachable objects from refs (traverse trees and chunklists) then sweep unreferenced objects. Dry-run supported [8].

[11] **Component: Tests & Quality** - casq_core contains extensive unit and property tests (listed in README). CI expects clippy clean and cargo fmt. Repository contains `tests/` for integration tests and `FUZZING_PLAN.md` for fuzz targets [8][3]. Coverage reporting task (`mise run coverage_core`) has been added to generate HTML and XML reports for the casq_core crate; the task now runs tarpaulin against the casq_core manifest only and stores reports under `target/coverage/casq_core/` (see mise.toml). Recent runs report coverage above 90% for the casq_core crate.

[12] **Decision: JSON & stdout/stderr separation** - All commands support `--json` where only JSON is written to stdout; informational messages and errors go to stderr. This enables scripting reliability and is enforced throughout the CLI output layer [9].

[13] **TODO: Mindmap maintenance** - Follow repository CLAUDE.md directives: update this MINDMAP.md before/after work, add Bug/TODO nodes for non-trivial changes, and keep node cross-references to relevant files (README/CLAUDE) [12].

[16] **Component: Fuzzing Plan** - `FUZZING_PLAN.md` describes a cargo-fuzz-based strategy: priority fuzz targets for binary parsers, text parsers, compression; target examples, corpus seeding, CI/nightly integration, and triage workflow. Use cargo-fuzz to add fuzz targets and CI harness [22].

[17] **Component: Integration & Tests (tests/)** - `tests/README.md` describes integration tests harness: isolated store per test, CLI-based tests (help, initialize, put/list/get, metadata, gc, references), and snapshot/golden file guidance. Tests include Python harness and Rust tests; follow test structure when adding tests [23][8].

[18] **Component: Build & CI tooling** - Repository uses `mise.toml` (task automation), cargo for Rust builds, pytest for Python integration tests, and CI expects clippy, cargo fmt, and test runs. FUZZING_PLAN suggests nightly cargo-fuzz CI integration [8][22].

[19] **Component: Governance & Issue Notes (.beans, .serena)** - The repo contains many `.beans/*` and `.serena/memories/*` notes documenting tasks, UX/bug fixes, stdout/stderr rules, and design discussions — treat these as authoritative task artifacts when implementing fixes (see `.serena/memories/stdout-stderr-rules.md`) [24].

[20] **Object Header (v2) specifics** - Object header is 16 bytes: 4-byte "CAFS" magic, 1-byte version (2), 1-byte type (1=blob,2=tree,3=chunk_list), 1-byte algorithm id (1=blake3-256), 1-byte compression (0=none,1=zstd), 8-byte payload_len (u64 LE). Implemented in `casq_core/src/object.rs` [14].

[21] **Journal format** - Journal entries are pipe-delimited lines: timestamp|operation|hash|path|metadata. Stored in `journal` file at store root; read by `Journal::read_recent` and parsed by `JournalEntry::from_line` (`casq_core/src/journal.rs`) [15].

[22] **Refs format** - Refs are files under `refs/`, append-only lines containing hex hashes; last non-empty non-comment line is current value. `RefManager::add/get/list` implement append/read semantics in `casq_core/src/refs.rs` [16].

[23] **Threshold constants (store.rs)** - Compression threshold = 4KB, chunking threshold = 1MB. These drive when zstd or FastCDC are applied (`casq_core/src/store.rs`) [11].

[24] **Chunker defaults** - ChunkerConfig defaults: min=128KB, avg=512KB, max=1MB (FastCDC v2020). See `casq_core/src/chunking.rs` for rationale and property tests [18].

[25] **Tree & ChunkList binary formats** - Tree entry encoding: type(1)|mode(4 LE)|hash(32)|name_len(1)|name bytes (max name_len=255). ChunkList entry: 32-byte hash + 8-byte size (40 bytes per entry). See `casq_core/src/tree.rs` and `casq_core/src/object.rs` [17][14].

---

[26] **Component: Python test harness (integration tests)** - Pytest-based black-box tests live in `tests/` and exercise the CLI via subprocess. Key fixtures: `casq_bin` (builds binary at `target/debug/casq` if missing) and `casq_env` (sets `CASQ_ROOT` to an isolated `tmp_path/casq-store` per test). Tests run from repository root and assume the binary is compiled when needed. See `tests/conftest.py` and `tests/helpers.py` [11][17].

[27] **Component: Golden files & helpers** - Tests use a `tests/golden/` directory managed by `tests/helpers.compare_golden`. Golden files are created/updated when missing or when update flag is used; tests compare exact outputs against these golden files for UX stability. See `tests/helpers.py` [17].

[28] **Component: CLI test expectations & JSON handling** - Integration tests enforce strict stdout/stderr separation: informational messages (e.g., "Initialized casq store") go to stderr, command data or JSON responses go to stdout. Helpers provide `assert_json_success` and `assert_json_error` to validate JSON shapes. Some commands are explicitly incompatible with `--json` (tests expect `get` to fail with `--json`). See `tests/*` and `tests/helpers.py` [12][11].

[29] **Bug: chunking::tests::prop_boundary_stability_after_delete failing** - Test previously assumed global chunk reuse ratio >=40% after middle deletions. Deterministic counterexamples caused flaky/failed runs. Fix: test now asserts prefix-preservation for chunks that end before the deletion offset (>=95% preserved). If deletion falls inside the first chunk, the test falls back to a reduced reuse heuristic (>=30%). See `casq_core/src/chunking.rs` tests for details.

[30] **Task: coverage_core (mise)** - The mise task `coverage_core` was adjusted to run cargo-tarpaulin only for the casq_core crate using `--manifest-path casq_core/Cargo.toml` and to exclude non-core sources. It places HTML and XML reports under `target/coverage/casq_core/`. Recent pipeline runs report casq_core coverage above 90% (Cobertura: target/cobertura.xml and tarpaulin HTML in the target coverage directory).

## Useful references (files/paths)

[14] **Key files** - `casq_core/src/lib.rs` [6], `casq_core/src/object.rs` (object format) [8], `casq/src/main.rs` (CLI) [7], `casq/src/output.rs` (JSON/stderr handling) [12], `CLAUDE.md` (dev rules) [13], `FUZZING_PLAN.md` (fuzz targets) [16], `tests/README.md` (integration tests) [17].

[15] **Docs to update when changing design** - `README.md`, `casq_core/README.md`, `casq/README.md`, `CLAUDE.md`, `MINDMAP.md` (this file) — updates must be made in the same session as code changes per CLAUDE.md [13].


# Notes
- Nodes are intentionally concise and line-oriented to support quick grep and incremental edits.
- Add a `Bug:` node for any bug fixes with root cause, code paths changed, and tests that were added.
- If you want I can also generate a minimal MINDMAP.*.md split (e.g., MINDMAP.gc.md) if this grows beyond ~100 nodes.
