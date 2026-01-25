---
# workspace-70j4
title: Implement fuzzing for parser hardening
status: draft
type: milestone
priority: normal
created_at: 2026-01-25T09:26:19Z
updated_at: 2026-01-25T09:26:19Z
---

Add coverage-guided fuzzing using cargo-fuzz to harden binary parsers against malformed/malicious input.

**Status:** Future work - implement AFTER property testing is complete

**Reference:** /workspace/FUZZING_PLAN.md

## Overview
- 7 fuzz targets for comprehensive parser robustness
- Framework: cargo-fuzz with libFuzzer backend
- Expected timeline: ~3 weeks after property testing

## Targets
1. object_header_decode (Priority 1)
2. chunk_list_decode (Priority 1)
3. tree_entry_decode (Priority 1)
4. journal_from_line (Priority 2)
5. hash_from_hex (Priority 2)
6. store_parse_config (Priority 2)
7. compression_roundtrip (Priority 3)

## Success Criteria
- Zero crashes after 4+ hours per target
- Nightly CI integration successful
- Corpus preserved for regression detection
- Coverage > 90% on parser modules

## Dependencies
- Property testing must be completed first
- cargo-fuzz installation
- CI/CD pipeline updates