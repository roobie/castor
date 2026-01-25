---
# casq-uohr
title: Fix casq list documentation bug
status: completed
type: bug
priority: high
created_at: 2026-01-25T14:15:44Z
updated_at: 2026-01-25T14:25:22Z
---

**Issue:** README.md and casq/README.md used command aliases that don't exist, causing all examples to fail.

**Impact:** CRITICAL - Every example in both README files used non-existent command names

**Root Cause:** Documentation was written using convenient aliases (init, add, cat, ls, stat, gc, etc.) but the CLI only implements full command names (initialize, put, get, list, metadata, collect-garbage, etc.)

## What Was Fixed

### Command Name Corrections (Applied Throughout Both READMEs):
- `casq init` → `casq initialize`
- `casq add` → `casq put` (also `--ref-name` → `--reference`)
- `casq cat` → `casq get`
- `casq stat` → `casq metadata`
- `casq gc` → `casq collect-garbage`
- `casq orphans` → `casq find-orphans`
- `casq refs` → `casq references`

### Critical: casq list vs references list
**Previously documented (INCORRECT):**
- `casq ls` - Lists all references
- `casq ls <hash>` - Lists tree contents

**Actual CLI behavior:**
- `casq list <hash>` - Lists tree contents (hash is REQUIRED)
- `casq references list` - Lists all references

### Other Fixes:
- `CASTOR_ROOT` → `CASQ_ROOT` (environment variable)
- Removed `journal` command examples (command doesn't exist)
- Fixed all JSON output section examples
- Updated all workflow examples
- Corrected `<PATH>...` to `<PATH>` (single path only)

## Files Updated
- ✅ /workspace/README.md
- ✅ /workspace/casq/README.md

## Verification
- ✅ All command names verified against `casq --help`
- ✅ Subcommand syntax verified against `casq <command> --help`
- ✅ Environment variable name confirmed in source code