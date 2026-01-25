---
# casq-em53
title: Create error message quality guidelines
status: todo
type: task
priority: low
created_at: 2026-01-25T14:16:01Z
updated_at: 2026-01-25T14:16:01Z
---

Define and document standards for CLI error messages.

**Deliverable:** /workspace/docs/ERROR_MESSAGE_GUIDELINES.md

## Review Process
1. Catalog all error messages from codebase (search for .with_context, bail!, Error::)
2. Review each for clarity, actionability, context
3. Rate on 5-star scale
4. Document improvements

## Rating Template
```
Error: "Failed to add path: /nonexistent"

Clarity: ★★★☆☆ (clear what failed, but no context)
Actionability: ★★☆☆☆ (doesn't suggest checking path exists)
Context: ★★★★☆ (shows the problematic path)

Improvement: "Failed to add path: /nonexistent (file or directory not found)"
```

## Guidelines to Define
1. Start with context (what failed)
2. Include relevant details (path, hash, name)
3. Suggest solution when obvious
4. No technical jargon
5. Consistent punctuation

## Error Categories
- Store initialization errors
- Path errors
- Hash validation errors
- Reference management errors
- Stdin handling errors
- JSON mode errors

## Deliverable
- Documented standards
- Reviewed error catalog
- Improvement recommendations