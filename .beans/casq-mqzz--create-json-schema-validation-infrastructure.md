---
# casq-mqzz
title: Create JSON schema validation infrastructure
status: todo
type: task
priority: high
created_at: 2026-01-25T14:15:48Z
updated_at: 2026-01-25T14:15:48Z
---

Define JSON schemas for all CLI outputs and implement validation tests.

**Deliverables:**
- 11 JSON schema files in /workspace/tests/schemas/
- Python test file: /workspace/tests/test_json_schemas.py

## Schemas to Create
1. initialize_output.schema.json
2. put_output.schema.json
3. list_tree.schema.json
4. list_blob.schema.json
5. metadata_output.schema.json
6. gc_output.schema.json
7. orphans_output.schema.json
8. refs_add.schema.json
9. refs_list.schema.json
10. refs_remove.schema.json
11. error_output.schema.json

## Base Schema Pattern
All schemas must require:
- success (boolean)
- result_code (integer, 0-255)

## Dependencies
- Python jsonschema library

## Test Implementation
For each command, capture JSON output and validate against schema.

## Verification
```bash
pytest tests/test_json_schemas.py -v
```

Should validate all 11 output types