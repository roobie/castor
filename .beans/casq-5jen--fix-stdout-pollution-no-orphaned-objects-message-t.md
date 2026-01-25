---
# workspace-5jen
title: 'Fix stdout pollution: ''No orphaned objects'' message to stderr'
status: todo
type: bug
priority: high
created_at: 2026-01-25T09:30:38Z
updated_at: 2026-01-25T09:31:12Z
parent: casq-uko9
---

The 'orphans' command writes an informational message to stdout when no orphans are found.

**Location:**
- casq/src/main.rs:617 - `cmd_orphans`: "No orphaned objects found\n"

**Expected behavior:**
- Stdout: Only orphan data (hashes, types) when orphans exist
- Stderr: Informational message when no orphans found

**Fix:**
This message should be written to stderr, not stdout. When there are no results, the command should output nothing to stdout (or empty JSON array in --json mode).

**Impact:** Breaks scriptability when checking for orphans