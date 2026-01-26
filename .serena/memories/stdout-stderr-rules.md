# stdout/stderr Separation Rules for casq CLI

## Critical Rule: JSON Mode
**In JSON mode (`--json` flag), ONLY JSON should ever go to stdout.**

- All JSON output → stdout
- All other messages (errors, warnings, informational) → stderr
- This ensures machine parsability: `casq --json command | jq`

## Text Mode Rules

### stdout: Data Output Only
- Command results (hashes, file content, listings)
- Concrete data that scripts might parse
- Examples: hashes from `put`, file content from `get`, tree listings from `list`

### stderr: Informational Messages
- Confirmations ("Initialized casq store...")
- Reference creation notifications
- Empty state messages ("No references", "No orphaned objects")
- Progress/status updates
- Errors and warnings

## Implementation Pattern

Use the OutputWriter abstraction:
- `output.write()` - Always writes to stdout (data output in both modes)
- `output.write_info()` - Writes to stderr in text mode, stdout in JSON mode (informational)
- `output.write_error()` - Always writes to stderr (errors in both modes)

Manual stderr writes should be conditional:
```rust
if !output.is_json() {
    writeln!(io::stderr(), "informational message")?;
}
```

## Testing

Tests should strictly validate separation:
```python
# Informational messages must be in stderr AND stdout must be empty
assert "informational message" in proc.stderr
assert proc.stdout == ""

# Data must be in stdout (and stderr typically empty)
assert expected_data in proc.stdout
```

Avoid lenient "or" assertions like:
```python
# BAD: too lenient
assert "msg" in proc.stderr or proc.stdout == ""
```

## Fixed Issues

### Code Fixes (casq/src/main.rs)
1. **cmd_init (line 194-200)**: Fixed manual stderr write to only run in text mode (not JSON mode), and fixed swapped format arguments (path first, then algorithm)
2. **cmd_put (line 271-277)**: Cleaned up reference name output formatting

### Test Fixes
1. **tests/test_references.py:16**: Changed from lenient OR to strict AND assertions
2. **tests/test_gc_orphans.py:111**: Changed from lenient OR to strict AND assertions
3. **tests/test_gc_orphans.py:206**: Changed from lenient OR to strict AND assertions

All 69 tests pass with the strict assertions.