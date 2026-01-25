---
# casq-zqis
title: Create documentation accuracy validation tests
status: todo
type: task
priority: normal
created_at: 2026-01-25T14:15:57Z
updated_at: 2026-01-25T14:15:57Z
---

Implement automated tests to ensure README examples work as written.

**Deliverable:** /workspace/tests/test_documentation.py

## Test Coverage (15 tests)
1. Extract all bash code blocks from README.md and casq/README.md
2. Execute examples (skip those with placeholders)
3. Verify expected behavior
4. Validate help text matches README descriptions
5. Check default values in help match actual behavior

## Test Implementation
```python
def test_readme_examples_executable():
    examples = extract_bash_blocks("README.md")
    for example in examples:
        if "<HASH>" in example or "..." in example:
            continue  # Skip placeholders
        result = subprocess.run(example, shell=True, capture_output=True)
        assert result.returncode in [0, 1]  # Expected codes

def test_help_text_matches_readme():
    help_output = run_casq(["--help"])
    # Extract and compare command descriptions

def test_default_values_accurate():
    # Compare help text defaults with actual behavior
```

## Benefits
- Prevents stale documentation
- Ensures examples stay current
- Catches breaking changes

## Verification
```bash
pytest tests/test_documentation.py -v
```

Should validate all README examples