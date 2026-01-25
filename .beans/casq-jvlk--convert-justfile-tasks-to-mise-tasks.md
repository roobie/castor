---
# casq-jvlk
title: Convert Justfile tasks to Mise tasks
status: completed
type: task
priority: normal
created_at: 2026-01-25T13:05:19Z
updated_at: 2026-01-25T13:08:28Z
---

Convert all tasks from justfile to mise.toml using TOML format, remove justfile, and update documentation.

## Checklist
- [x] Read current justfile and mise.toml
- [x] Update mise.toml with all task definitions
- [x] Remove justfile
- [x] Update CLAUDE.md to reference mise instead of just
- [x] Test the migration
- [x] Commit changes with bean file