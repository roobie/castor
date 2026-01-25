---
# workspace-7ov8
title: 'Fix stdout pollution: ''No journal entries'' messages to stderr'
status: todo
type: bug
priority: high
created_at: 2026-01-25T09:30:38Z
updated_at: 2026-01-25T09:31:14Z
parent: casq-uko9
---

The 'journal' command writes informational messages to stdout when no entries are found.

**Locations:**
- casq/src/main.rs:704 - `cmd_journal`: "No orphaned journal entries found\n"
- casq/src/main.rs:706 - `cmd_journal`: "No journal entries\n"

**Expected behavior:**
- Stdout: Only journal entry data when entries exist
- Stderr: Informational messages when no entries found

**Fix:**
These messages should be written to stderr. Empty results should output nothing to stdout (or empty JSON array in --json mode).

**Impact:** Breaks scriptability for journal queries