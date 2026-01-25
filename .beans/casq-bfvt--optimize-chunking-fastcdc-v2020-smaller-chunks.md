---
# casq-bfvt
title: 'Optimize chunking: FastCDC v2020 + smaller chunks'
status: in-progress
type: feature
created_at: 2026-01-25T20:18:35Z
updated_at: 2026-01-25T20:18:35Z
---

Upgrade from FastCDC Ronomon to v2020 variant and reduce min chunk size from 256KB to 128KB for better incremental deduplication.

## Goal
When large files (≥1MB) are slightly modified, achieve 60-80% chunk reuse instead of current ~0%.

## Checklist

- [x] Update chunking algorithm in casq_core/src/chunking.rs (Ronomon → v2020)
- [x] Reduce min_size from 256KB to 128KB
- [x] Add property-based tests for boundary stability
- [x] Add Python integration tests for deduplication
- [x] Update /workspace/README.md
- [x] Update /workspace/casq_core/README.md
- [x] Update /workspace/CLAUDE.md
- [x] Update /workspace/NOTES.md
- [x] Create /workspace/IMPLEMENTATION_SUMMARY.md
- [x] Run manual verification test (not needed - automated tests cover this)
- [x] Verify all Rust tests pass (124 tests, 100% pass rate)
- [x] Verify all Python tests pass (69 tests, 100% pass rate)