---
# casq-54by
title: Add 'casq references query' command with regex filtering
status: todo
type: feature
created_at: 2026-01-25T21:42:56Z
updated_at: 2026-01-25T21:42:56Z
---

Implement a new CLI command 'casq references query' that accepts a regex pattern to filter references by name.

## Requirements
- New subcommand under 'casq references query <REGEX>'
- Accept regex pattern as argument
- Filter reference names matching the pattern
- Display matching references in standard format
- Support --long flag for detailed output
- Support --json flag for machine-readable output

## Technical Considerations
- Use Rust regex crate for pattern matching
- Handle invalid regex patterns with clear error messages
- Consistent with existing 'casq refs list' output format
- Follow existing CLI patterns in casq