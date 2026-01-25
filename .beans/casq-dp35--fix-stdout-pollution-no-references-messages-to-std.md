---
# casq-dp35
title: 'Fix stdout pollution: ''No references'' messages to stderr'
status: in-progress
type: bug
priority: high
created_at: 2026-01-25T09:30:38Z
updated_at: 2026-01-25T11:46:45Z
parent: casq-uko9
---

Informational messages about empty results are being written to stdout instead of stderr, breaking proper CLI output separation.

**Problem:** When there are no references, the CLI writes informational messages to stdout. This pollutes the data stream and breaks pipelines.

**Locations:**
- casq/src/main.rs:386 - `cmd_ls`: "No references (use 'casq add --ref-name' to create one)\n"
- casq/src/main.rs:773 - `cmd_refs_list`: "No references\n"

**Expected behavior:**
- Stdout: Only data output (hashes, paths, JSON results)
- Stderr: All informational messages, warnings, confirmations

**Fix:**
These messages should be written to stderr via a new method like `output.write_info()` or similar.

**Impact:** High - breaks scriptability and pipeline usage