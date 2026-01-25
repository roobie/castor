---
# casq-uko9
title: Fix CLI stdout/stderr separation
status: todo
type: epic
priority: high
created_at: 2026-01-25T09:30:50Z
updated_at: 2026-01-25T09:30:50Z
---

The CLI violates the Unix principle of separating data output (stdout) from informational messages (stderr). This breaks scriptability and pipeline usage.

## Problem
Informational messages like "No references", "Created reference", etc. are being written to stdout instead of stderr. This pollutes the data stream when piping output.

## Impact
- Users cannot reliably pipe command output
- Scripts break when checking for empty results
- Violates standard CLI conventions

## Solution
Implement proper output separation:
- **Stdout:** Only actual result data (hashes, paths, JSON)
- **Stderr:** All informational messages, warnings, confirmations

## Implementation
Add a new method to OutputWriter (e.g., `write_info`) that:
- In text mode: writes to stderr
- In JSON mode: possibly suppresses (since JSON output includes all data)

## Related Bugs
See child beans for specific instances