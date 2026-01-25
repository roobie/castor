---
# casq-vepb
title: Create cross-platform compatibility tests
status: todo
type: task
priority: normal
created_at: 2026-01-25T14:15:56Z
updated_at: 2026-01-25T14:15:56Z
---

Implement tests to validate CLI works correctly on Linux, macOS, and Windows.

**Deliverable:** /workspace/tests/test_cross_platform.py

## Test Coverage (20 tests)
1. Path separator handling (/ vs \)
2. Line ending consistency (LF vs CRLF)
3. Unicode path handling (Cyrillic, Chinese, emoji)
4. Case sensitivity behavior
5. Platform-specific defaults

## Platform Matrix
- Linux (bash, zsh)
- macOS (zsh, bash)
- Windows (cmd, PowerShell)

## Test Examples
```python
def test_path_separators(platform):
    if platform == "windows":
        path = "C:\\Users\\test\\file.txt"
    else:
        path = "/tmp/test/file.txt"
    result = run_casq(["put", path])
    assert result.returncode == 0

def test_unicode_paths():
    test_paths = [
        "файл.txt",  # Cyrillic
        "文件.txt",  # Chinese
        "🎉emoji🎉.txt",  # Emoji
    ]
    for path in test_paths:
        # Test add and materialize
```

## CI Integration
Run in matrix across ubuntu-latest, macos-latest, windows-latest

## Verification
```bash
pytest tests/test_cross_platform.py -v
```

Should pass on all 3 platforms