---
# casq-fgc7
title: Fix stdout/stderr test expectations
status: completed
type: task
priority: normal
created_at: 2026-01-26T14:56:14Z
updated_at: 2026-01-26T15:18:04Z
---

Update tests in tests/ directory to correctly validate stdout/stderr separation:
- stdout: Only relevant data (command output, file content, JSON results)
- stderr: All informational messages and notifications

## Checklist
- [x] Understand current stdout/stderr behavior in the CLI by reading casq/main.rs (clap CLI)
- [x] Identify which tests have incorrect expectations
- [x] Update test assertions for stdout/stderr
- [x] Verify documentation matches implementation
- [x] Run all tests to confirm fixes (`mise run test`)
