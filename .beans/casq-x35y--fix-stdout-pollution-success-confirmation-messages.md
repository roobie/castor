---
# workspace-x35y
title: 'Fix stdout pollution: Success confirmation messages to stderr'
status: todo
type: bug
priority: normal
created_at: 2026-01-25T09:30:39Z
updated_at: 2026-01-25T09:31:16Z
parent: casq-uko9
---

Success confirmation messages for write operations are being written to stdout instead of stderr.

**Locations:**
- casq/src/main.rs:286 - `cmd_add`: "Created reference: {} -> {}\n"
- casq/src/main.rs:328 - `cmd_materialize`: "Materialized {} to {}\n"
- casq/src/main.rs:801 - `cmd_refs_rm`: "Removed reference: {}\n"

**Expected behavior:**
- Stdout: Only the actual result data (e.g., hash and path for 'add')
- Stderr: Success/confirmation messages

**Rationale:**
Success confirmations are informational metadata, not data output. They should go to stderr to keep stdout clean for piping/processing.

**Example:**
```bash
# Current (broken)
casq add file.txt | somecommand  # pipes "Created reference: ..." 

# Expected
casq add file.txt | somecommand  # only pipes hash and path
```

**Impact:** Medium - affects scriptability when using --ref-name or other operations