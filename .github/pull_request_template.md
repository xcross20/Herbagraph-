## HerbaGraph change

### Linked task

Closes #

### Handoff

```text
HERBAGRAPH_IMPLEMENTATION_REPORT
Task: HG-###
Status: READY_FOR_ARCHITECT
Commit: replace-with-full-head-sha
```

### User-visible outcome

Describe what changes for an individual, clinician, operator, or reviewer.

### Implementation

- 

### Invariants checked

- [ ] Case remains the longitudinal source of truth
- [ ] Evidence is attached only to relevant branches
- [ ] Non-addressing evidence cannot close a branch
- [ ] Repeated execution is idempotent
- [ ] Corrections preserve linked history
- [ ] No diagnostic probability or unsupported certainty was added
- [ ] Existing lab engine was reused rather than duplicated
- [ ] Safety, provenance, owner scoping, and audit behavior remain intact

### Validation

```text
exact command
exact result
```

### Hostile-path tests

- [ ] Repeated or non-informational turn
- [ ] Correction and rebuild
- [ ] Unrelated test/branch
- [ ] Non-addressing evidence
- [ ] Malformed external or LLM input
- [ ] Concurrency where applicable

### Database and deployment

- Migration: none
- Rollback:
- Deployment impact:

### Security, privacy, and PHI

- Impact: none

### Known limitations

- None

### Review state

- [ ] Ready for Architect review
- [ ] Architect approved exact head SHA
- [ ] Founder approval obtained where required
