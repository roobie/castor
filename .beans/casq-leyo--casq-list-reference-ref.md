---
# casq-leyo
title: casq FOO --reference <REF>
status: todo
type: task
priority: normal
created_at: 2026-01-26T13:35:04Z
updated_at: 2026-01-26T13:39:00Z
---

Add support for --reference in casq list, get, metadata and materialize, so that one does not need to juggle hashes

E.g.
```bash
casq list --reference my-ref
casq get --reference my-ref
casq metadata --reference my-ref
casq materialize --reference my-ref <TARGET>
```

Also allow for short arg `-r`, which means we need to change --root to have short arg `-R`
Backwards compatibility is not an issue, since the tool is pre-release and has no users yet.
