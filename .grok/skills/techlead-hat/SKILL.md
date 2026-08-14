---
name: techlead-hat
description: >
  Tech Lead Hat — PR descriptions, ADRs, commit messages, handoffs. Answer,
  then reasoning, then risk. Use when the user runs /techlead-hat, asks for
  a PR description, commit message, handoff, or definition of done.
metadata:
  short-description: "Tech lead hat: artifacts for the 3 a.m. reader"
---

# Tech Lead Hat

Read `../engineering-operating-manual/references/8-techlead-hat.agent.md` and Part VIII of the manual.

Governing law: **answer, then reasoning, then risk** — for the reader who reads three sentences.

## Forbidden

- No journey narration.
- No summary more confident than the analysis beneath it.
- No handoff without the trap line.

## Artifacts

**PR / ship note:**

```
## [What & why — one act-on-able sentence]
**Verification:** [claims → tests]
**Risk:** [top scenario, mitigation, tripwire, rollback + strands]
**Not covered:** [declared gaps]
```

**Commit message:** the claim + the why that is not in the diff.

**Handoff (whenever work pauses):**

```
**State:** [done vs verified vs merely written]
**Next action:** [single concrete step]
**Open risks:** [...]
**The trap:** [the one thing resumption would assume that is FALSE]
```

Definition of done: every acceptance claim has a once-red test; top risk has mitigation + test + tripwire; cold review has a written verdict; rollback stated with strands; handoff has a trap line. Name any missing item — that item means the work is not done.
