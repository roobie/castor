## High-Level Concept

A small, single-binary **content-addressed store**:

- Stores files/dirs by hash (e.g. options: XXH3 for speed or BLAKE3 if cryptographic security is needed).
- Returns a stable content hash (CID-like).
- Can reconstruct trees, list contents, and garbage-collect unreferenced data.
- Local-only, single-user, no network.

Think “minimal git object store / restic backend” but generic and simple.

---

## Storage Model (MVP)

- **Objects directory**:
  - `store_root/objects/<algo>/<first2>/<rest...>`
  - Each object is immutable, named by its hash.
- **Types of objects**:
  - **blob**: raw file content.
  - **tree**: directory description (list of entries).
  - **manifest** (optional later): metadata wrapper.

Example `tree` encoding (MVP, text or binary):

- One line per entry: `<mode> <type> <hash> <name>\n`
- `mode`: `100644`, `100755`, `040000`
- `type`: `blob` or `tree`
- `hash`: hex-encoded
- `name`: filename

You can evolve the format later; just version it.

---

## Basic CLI Design

I’ll use a binary name `castore` for concreteness.

### Global Layout

- `castore init [--root PATH]`
- `castore add PATH...`
- `castore materialize HASH DEST`
- `castore cat HASH`
- `castore ls HASH`
- `castore gc [options]`
- `castore refs [subcommands]` (optional in MVP)
- `castore stat HASH`

All commands accept `--store-root` (env var fallback like `CASTORE_ROOT`).

---

## Commands (MVP Scope)

### 1. `init`

Initialize a new store.

**Usage:**

```bash
castore init [--root PATH] [--algo blake3|sha256]
```

**Behavior (MVP):**

- Creates directory structure:
  - `PATH/objects/`
  - `PATH/config` (stores algo, version)
- Fails if already initialized (unless `--force`).

---

### 2. `add`

Add files or directories to the store. Returns a root hash.

**Usage:**

```bash
castore add PATH...
# or
castore add --stdin
```

**Behavior:**

- If path is a **file**:
  - Reads file, chunks (or just whole file for MVP), computes hash.
  - Stores as `blob`.
  - Prints hash: `HASH  PATH`.
- If path is a **directory**:
  - Recursively walks directory.
  - For each file: store as blob.
  - For each subdir: build a tree object.
  - Root directory has its own `tree` object.
  - Prints root tree hash.
- `--stdin`:
  - Reads from stdin, stores a single blob, prints hash.

**Options (MVP):**

- `--follow-symlinks` (default: error on symlink or ignore).
- `--no-metadata` (MVP default: ignore ownership/mtime; store only mode+name).

---

### 3. `materialize`

Reconstruct a tree, blob, or file hierarchy from a hash.

**Usage:**

```bash
castore materialize HASH DEST
```

**Behavior:**

- If `HASH` is a **blob**:
  - Writes file at `DEST` (must be file or `-` for stdout).
- If `HASH` is a **tree**:
  - Creates directory structure under `DEST`.
  - Recreates files and subdirs based on tree entries.
- Preserves *basic* permissions (`mode`) in MVP.

---

### 4. `ls`

List contents for a tree, or show basic info for a blob.

**Usage:**

```bash
castore ls HASH
```

**Behavior:**

- If tree:
  - Lists entries: `<mode> <type> <short-hash> <name>`
- If blob:
  - Prints: `blob <size> <hash>`

Optional flags later:

- `--json`
- `--recursive`

---

### 5. `cat`

Output blob contents to stdout.

**Usage:**

```bash
castore cat HASH
```

**Behavior:**

- Valid only for `blob` types.
- Streams content to stdout.

---

### 6. `stat`

Show metadata about an object.

**Usage:**

```bash
castore stat HASH
```

**Behavior:**

- Type: `blob` or `tree`
- Size (bytes, for blob; encoded size, for tree)
- Maybe: number of entries if tree.

Example:

```text
Type: blob
Hash: 7f9c2ba4...
Size: 1024 bytes
```

---

### 7. `gc` (simple MVP)

Garbage collect unreferenced objects based on refs file(s).

**MVP assumption**: there is a simple refs DB:

- `store_root/refs/` directory with files:
  - e.g. `refs/root-1`, `refs/root-2` containing hashes (one per line).
- Anything reachable from those roots is “live”.

**Usage:**

```bash
castore gc [--dry-run]
```

**Behavior:**

- Build set of live objects by walking from all refs.
- Delete all objects not in that set.
- `--dry-run`: print what would be deleted.

You can add:

```bash
castore refs add NAME HASH
castore refs list
castore refs rm NAME
```

…as a small extension if desired for MVP.

---

## Minimal Internal Data Structures (Zig)

Rough high-level modules:

- `hash.zig`
  - Wrapper around chosen hash (BLAKE3).
  - `fn hash_bytes([]const u8) -> Hash`
  - `fn hash_file(path: []const u8) -> !Hash`
- `store.zig`
  - Knows about `StoreRoot` path, layout.
  - `fn init(root: []const u8, algo: Algorithm) -> !void`
  - `fn put_blob(reader: anytype) -> !Hash`
  - `fn get_blob(hash: Hash, writer: anytype) -> !void`
  - `fn put_tree(entries: []TreeEntry) -> !Hash`
  - `fn get_tree(hash: Hash) -> ![]TreeEntry`
  - `fn object_type(hash: Hash) -> !ObjectType`
- `walk.zig`
  - Filesystem walkers for `add` (dir to tree).
- `cli.zig`
  - Arg parsing, subcommand dispatch.
- `gc.zig`
  - Reachability from refs, deletion.

---

## MVP Features Checklist

**Include in MVP:**

1. `init`, `add`, `materialize`, `cat`, `ls`, `stat`, `gc`.
2. Hashing: **BLAKE3 only** initially.
3. Simple, contiguous blobs (no chunking/dedup within files).
4. Tree objects with mode/type/name/hash.
5. Refs as plain text files in `refs/`.
6. Basic errors: unknown hash, corrupted object, invalid store root.

**Exclude / postpone:**

- Chunked blobs with dedup (e.g. rolling hash).
- Compression of blobs/trees.
- Extended metadata (owners, group, xattrs, timestamps).
- Transactions/concurrency.
- Network protocols / remote stores.
- Encryption.

---

## Rough Effort / Complexity Estimate

Assuming you’re comfortable in Zig but not an expert:

- **Core hashing + storage layout**: 0.5–1 day
- **Blob add/get (`add`, `cat`)**: 1 day
- **Tree encoding/decoding + directory add/materialize**: 2–3 days
- **CLI and argument parsing**: 1 day
- **GC + refs**: 1–2 days
- **Tests + basic fuzzing for tree parsing**: 1–2 days
- **Polish (error messages, help text, docs)**: 1 day

Realistically, a **usable MVP**: about **1.5–2 weeks of part-time work**, or **3–5 focused days** if you go quickly and keep scope tight.

---

## Next Step

If you like this direction, I can:

- Draft the **on-disk object formats** concretely (exact bytes for blob & tree).
- Or sketch a small **Zig project layout** with function signatures for each command.
## Goals for the on‑disk format

- Simple, stable, and easy to parse.
- Friendly to append-only / immutable semantics.
- Human-inspectable enough with hexdump, but still compact.
- Versioned so you can evolve later.

I’ll define:

- Store layout
- Object file layout (blob / tree)
- Hash format
- Refs and config

---

## Store Directory Layout

Assume a root like:

```text
$STORE_ROOT/
  config
  objects/
    blake3/
      ab/
        abcd... (object file)
  refs/
    some-name
    another-name
```

- `config`: store config (algorithm, version).
- `objects/<algo>/<prefix>/<rest>`: object files keyed by hash.
- `refs/`: text files with root hashes.

---

## Hash Format

**Internal representation:**

- Use BLAKE3-256 (32 bytes).
- Store as raw 32 bytes for hashing/computation.
- Represent as lowercase hex string when used in filenames / CLI:

Example:

- Raw: `[32]u8`
- Hex: `2b7e151628aed2a6abf7158809cf4f3c...` (64 hex chars)

**File layout based on hash:**

- Hex string: `HHHHHHHH...` (64 chars).
- File path:  

  - First 2 hex chars → `prefix` dir
  - Remaining 62 chars → filename

Example:

- Hash (hex): `2b7e151628aed2a6abf7158809cf4f3c42d...`
- Path: `objects/blake3/2b/7e151628aed2a6abf7158809cf4f3c42d...`

---

## Object File Common Header

All objects start with the same header, then type-specific payload.

### Header layout (binary)

```text
offset  size  field
------  ----  -----------------------------
0       4     magic = "CAFS" (0x43 41 46 53)
4       1     version (u8), MVP: 1
5       1     type (u8): 1=blob, 2=tree
6       1     algo (u8): 1=blake3-256
7       1     reserved (u8), must be 0 for now
8       8     payload_len (u64, little-endian)
16      ...   payload (blob or tree-specific)
```

- `magic`: fixed `0x43 41 46 53` = `"CAFS"`.
- `version`: for format evolution.
- `type`:
  - `1` → blob
  - `2` → tree
- `algo`:
  - `1` → BLAKE3-256
- `payload_len`: number of bytes following (for sanity checks, streaming).

---

## Blob Object Format

### Semantics

- Represents raw file content.
- Hash is `algo(payload)` (i.e. hash just the payload, **not** the header).
- Header is redundant but allows for on-disk introspection.

### Layout

```text
0x00  4   "CAFS"
0x04  1   version = 1
0x05  1   type = 1  (blob)
0x06  1   algo = 1  (blake3-256)
0x07  1   reserved = 0
0x08  8   payload_len = file size in bytes (u64 LE)
0x10  N   payload: raw file bytes
```

No extra metadata in MVP (no filename, no timestamps).

---

## Tree Object Format

### Semantics

- Represents a directory listing.
- Contains multiple **entries**, each describing either:
  - a blob (file) or
  - a tree (subdirectory).
- The tree’s hash is `algo(payload)` (payload starts at offset `0x10`).

### Encoding

Binary, record-based format:

```text
payload:
  +--------------------------+
  | entry[0]                |
  +--------------------------+
  | entry[1]                |
  +--------------------------+
  | ...                     |
  +--------------------------+
```

Each **entry**:

```text
offset  size  field
------  ----  -----------------------------
0       1     type (u8): 1=blob, 2=tree
1       4     mode (u32, little-endian, POSIX-style)
5       32    hash (raw 32-byte BLAKE3 digest)
37      1     name_len (u8)
38      N     name bytes (UTF-8, length = name_len)
38+N    ...   next entry, if any
```

- `type`:
  - `1` → blob (file)
  - `2` → tree (directory)
- `mode`: POSIX-style file mode bits:

  - Typically:
    - `0o100644` regular file
    - `0o100755` executable file
    - `0o040755` directory
  - Store as `u32` with the **full** mode value.

- `hash`: raw 32-byte content hash of the target object (blob or tree).
- `name_len`: up to 255 bytes; enough for MVP.
- `name`: no null terminator; not zero-padded.

**Ordering:** 

- MVP: keep entries sorted lexicographically by name (bytewise, UTF-8).
- This guarantees stable tree hashes independent of traversal order.

### Full tree object layout

```text
0x00  4   "CAFS"
0x04  1   version = 1
0x05  1   type = 2  (tree)
0x06  1   algo = 1  (blake3-256)
0x07  1   reserved = 0
0x08  8   payload_len = total size of all entries
0x10  M   sequence of entry records as above
```

Parsing is:

1. Read header.
2. While cursor < `0x10 + payload_len`:
   - Read `type`, `mode`, `hash`, `name_len`, `name`.
   - Construct in-memory `TreeEntry`.

---

## Config File Format

`$STORE_ROOT/config` – simple key-value text, for MVP:

```text
version=1
algo=blake3-256
```

Later you can extend:

```text
chunking=none
compression=none
```

Parsing rule: `key=value` per line, `#` for comments, ignore unknown keys.

---

## Refs Format

Refs live in `$STORE_ROOT/refs/`.

### Reference file

- Each file under `refs/` is a named reference.
- Content: one or more lines, each with a hex hash.

MVP rules:

- Treat the **last non-empty line** in the file as the current ref value.
- Ignore blank lines, `#` comments allowed.

Example `refs/backup-2026-01-21`:

```text
# Root snapshot for 2026-01-21
2b7e151628aed2a6abf7158809cf4f3c42d1fff2a1b3c4d5e6f708090a0b0c0d
```

Your `gc` walks from all ref hashes in all files.

---

## Hashing Rules (Canonicalization)

To keep everything consistent:

- **Blob hash**:
  - `hash = blake3(payload_bytes)`

- **Tree hash**:
  - Steps:
    1. Collect all entries from filesystem.
    2. Normalize entry list:
       - Sort by `name` (bytewise compare).
       - For each file/dir: choose `type`, `mode` consistently.
    3. Serialize entries into a byte buffer according to the tree entry format.
    4. `hash = blake3(tree_payload_bytes)`.

- **Object file location**:
  - `hex = hex_encode(hash_bytes)`
  - `dir = hex[0..2]`
  - `file = hex[2..]`
  - `path = $STORE_ROOT/objects/blake3/$dir/$file`

Header is *not* part of the hashed content. You can always recompute and verify that the payload hash matches the filename.

---

## Sanity Checks & Corruption Detection

When reading an object:

1. Check header:
   - `magic == "CAFS"`,
   - `version == 1`,
   - `algo == expected` (from config),
   - `type ∈ {1,2}`.
2. Check that actual file size equals `16 + payload_len`.
3. Recompute hash of payload:
   - Confirm it matches object file name (hex).
4. For tree:
   - Ensure no overrun while parsing entries.
   - `name_len > 0`, `type` in `1..2`.

That’s enough for a robust MVP.

---

If you want, next step I can sketch the minimal Zig structs and encode/decode functions to match this exact layout.
