---
# casq-3jya
title: Create error message quality tests
status: todo
type: task
priority: high
created_at: 2026-01-25T14:15:51Z
updated_at: 2026-01-25T14:15:51Z
---

Implement comprehensive tests for CLI error message quality.

**Deliverable:** /workspace/tests/test_error_messages.py

## Error Categories to Test (50 tests)
1. Initialization errors (already initialized, permission denied)
2. Path errors (not found, already exists)
3. Hash errors (invalid format, wrong length, not found)
4. Reference errors (not found, invalid name)
5. Store errors (not initialized, corrupt config)
6. Stdin errors (TTY detection)
7. JSON mode errors (binary data with --json)

## Test Pattern
```python
@pytest.mark.parametrize("error_type,command,expected_content", [
    ("file_not_found", "put /nonexistent",
     ["Failed to add path", "/nonexistent"]),
    ("invalid_hash", "list abc123",
     ["Invalid hash"]),
])
def test_error_message_quality(error_type, command, expected_content):
    result = run_casq(command, expect_error=True)
    for expected in expected_content:
        assert expected in result.stderr
```

## Quality Criteria
- Errors explain what failed
- Errors include relevant details (path, hash, name)
- Errors suggest solutions when obvious
- No internal jargon exposed

## Verification
```bash
pytest tests/test_error_messages.py -v
```

Should pass 50 error quality tests