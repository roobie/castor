---
# casq-r6oy
title: Conduct First-Time User Experience (FTUX) sessions
status: todo
type: task
priority: low
created_at: 2026-01-25T14:15:59Z
updated_at: 2026-01-25T14:15:59Z
---

Run structured usability testing with new users to validate CLI UX.

**Goal:** Measure if users can complete basic workflows without documentation

## Protocol
**Participants:** 3-5 developers unfamiliar with casq

**Tasks:**
1. Create a store
2. Add a file with a named reference
3. List references
4. Restore the file to a new location
5. Remove the reference and free space

**Measurements:**
- Time to completion
- Number of help invocations
- Errors before success
- Overall success rate

**Target:** >80% success rate without docs

## Process
1. Give participant casq binary (no docs)
2. Provide task list
3. Observe (think-aloud protocol)
4. Record metrics
5. Debrief for qualitative feedback

## Deliverable
- FTUX test report with findings
- List of UX pain points
- Recommendations for improvements

## Notes
- This is manual testing (not automated)
- Schedule when Phase 1 automated tests are complete
- Results inform future UX improvements