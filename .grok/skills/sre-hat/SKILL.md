---
name: sre-hat
description: >
  SRE Hat — signals, logs, rollback, dark launch, tripwires. Code is not done
  when it works; it is done when you can tell whether it is working and undo
  it. Use when the user runs /sre-hat, asks to deploy, operate, roll back,
  or configure Railway/production.
metadata:
  short-description: "SRE hat: know if it is lying, and undo it"
---

# SRE Hat

Read `../engineering-operating-manual/references/7-sre-hat.agent.md` and Part VII of the manual.

Founding axiom: **the code is not done when it works; it is done when you can tell whether it is working, and undo it when it isn't.**

## Forbidden

- No deploy without a written rollback answer, including what rollback strands.
- No feature ships observable only by CPU/RAM.
- No secrets, tokens, or personal data in logs.

## Procedure

1. Health signals: success/failure, latency, **correctness** aimed at the top silent failure.
2. Logs that let an investigator rule something out.
3. Rollback before rollout. New storage shapes need expand/contract.
4. Ship dark, then ramp. Deploying code and changing behavior must not share a timestamp when you can avoid it.
5. Tripwires: signal + threshold + first move.

On HerbaGraph production: Railway project `charming-charisma`, web `Herbagraph-`, `Worker Service`, Redis. After catalog/evidence changes run `bash scripts/ops_reseed.sh`. Never report a Railway deploy successful without `SUCCESS` on `railway deployment list`.

## Artifact

```
## OPS PLAN: [title]
**Signals:** [...]
**Rollback:** [mechanism, time-to-undo, what it strands]
**Launch:** [...]
**Tripwires:** [signal + threshold + first move]
```

End with: "Ops plan complete. Next: Tech Lead hat."
