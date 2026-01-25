---
# casq-ce4v
title: Add CI workflow for UX tests
status: todo
type: task
priority: normal
created_at: 2026-01-25T14:15:58Z
updated_at: 2026-01-25T14:15:58Z
---

Create GitHub Actions workflow to run UX tests on all platforms.

**Deliverable:** .github/workflows/ux_tests.yml

## Workflow Configuration
```yaml
jobs:
  ux-tests:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - Checkout and build
      - Rust CLI integration tests (cargo test --test cli_ux_tests)
      - Python UX tests (pytest tests/)
      - Shell tests (bash tests/test_ux.sh - Unix only)
      - JSON schema validation
      - Snapshot verification
```

## Triggers
- Push to main/master
- Pull requests
- Manual workflow dispatch

## Test Execution
1. Build casq binary
2. Run Rust CLI tests
3. Run Python test suite
4. Validate JSON schemas
5. Check snapshot consistency
6. Generate test report

## Dependencies
This task depends on:
- casq-jxkf (Rust CLI tests)
- casq-jxkg (JSON schemas)
- casq-jxkh (Error message tests)
- casq-jxki (Snapshot tests)

## Verification
- Push change and verify workflow runs
- Check test results across all platforms