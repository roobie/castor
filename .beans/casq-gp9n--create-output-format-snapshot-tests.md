---
# casq-gp9n
title: Create output format snapshot tests
status: todo
type: task
priority: normal
created_at: 2026-01-25T14:15:55Z
updated_at: 2026-01-25T14:15:55Z
---

Implement snapshot testing to prevent output format regressions.

**Deliverable:** /workspace/tests/test_output_snapshots.py + snapshot files

## Snapshots to Create (10 baseline files)
```
tests/snapshots/
├── initialize_success.json
├── put_text_output.txt
├── put_json_output.json
├── references_list_empty.txt
├── references_list_populated.txt
├── list_tree_short.txt
├── list_tree_long.txt
├── metadata_blob.txt
├── gc_dry_run.txt
└── error_invalid_hash.txt
```

## Purpose
- Detect unintended output format changes
- Force explicit review when formats change
- Maintain backward compatibility

## Test Implementation
1. Run command and capture output
2. Compare against committed snapshot
3. Fail if differs (unless --update-snapshots flag)

## Verification
```bash
pytest tests/test_output_snapshots.py --snapshot-check
```

Should validate 30+ snapshot comparisons