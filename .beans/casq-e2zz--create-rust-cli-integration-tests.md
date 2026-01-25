---
# casq-e2zz
title: Create Rust CLI integration tests
status: todo
type: task
priority: high
created_at: 2026-01-25T14:15:45Z
updated_at: 2026-01-25T14:15:45Z
---

Create comprehensive CLI integration tests in Rust using assert_cmd.

**Deliverable:** /workspace/casq/tests/cli_ux_tests.rs

## Test Coverage (30 tests)
- Output format validation (text vs JSON modes)
- Help text validation (all commands listed)
- Error message quality (suggest --help, clear messages)
- Exit code consistency (matches JSON result_code)
- Global options available in all commands

## Dependencies to Add
```toml
[dev-dependencies]
assert_cmd = "2.0"
predicates = "3.0"
tempfile = "3.24"  # Already exists
```

## Example Tests
- test_help_text_shows_all_commands
- test_text_mode_stdout_stderr_separation
- test_json_mode_stdout_only
- test_error_exit_code_is_one
- test_missing_required_args_suggests_help

## Verification
```bash
cargo test --test cli_ux_tests
```

Should pass 30 tests