---
# workspace-bm2s
title: Implement file permission restoration in materialize
status: todo
type: bug
priority: normal
created_at: 2026-01-25T09:26:19Z
updated_at: 2026-01-25T09:26:19Z
---

When materializing objects, file permissions from the tree entry mode are not being properly set on the restored files.

**Location:** casq_core/src/store.rs:576

**Current behavior:** File permissions are not restored
**Expected behavior:** Set file permissions based on mode stored in tree entry

**Code reference:**
```rust
// TODO: Set file permissions based on mode stored in tree entry
```

This affects the fidelity of restored directory structures.