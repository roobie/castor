---
# casq-bulz
title: remove support for v1 format (it was never released)
status: completed
type: task
priority: normal
created_at: 2026-01-25T11:27:44Z
updated_at: 2026-01-25T16:21:21Z
---

Remove all v1 format support from the codebase since it was never released in a stable version.

## Checklist

- [x] Remove v1 format documentation from object.rs
- [x] Remove v1 version check from ObjectHeader::decode
- [x] Remove v1 reserved byte handling logic
- [x] Remove v1-specific tests
- [x] Update CLAUDE.md to remove v1/backward compatibility references
- [x] Update casq_core/README.md to remove v1 format documentation
- [x] Run tests to ensure everything still works
- [x] Update bean file to check off completed items