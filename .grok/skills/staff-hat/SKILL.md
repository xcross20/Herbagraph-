---
name: staff-hat
description: >
  Staff Engineer Hat — ranked risk map and spike the scariest unknown.
  Forbidden: category-level risks or uniform effort. Use when the user runs
  /staff-hat, /risk-map, or asks where this will break.
metadata:
  short-description: "Staff hat: risk = P × cost × invisibility"
---

# Staff Engineer Hat

Read `../engineering-operating-manual/references/3-staff-hat.agent.md` and Part III of `../engineering-operating-manual/references/engineering-operating-manual.md`.

**Risk = probability × cost × INVISIBILITY.** Invisibility dominates.

## Forbidden

- No category risks ("error handling"). Every entry is a scenario.
- No all-red maps. Re-rank until there is a top.
- No implementation before top-of-map unknowns are spiked.

## Standing hotspots

1. Boundaries between systems
2. Shared state
3. Time
4. Concurrency
5. Error paths
6. Config / environment
7. Migrations / persisted data (unrecoverable)
8. The freshly changed (blast radius, not just the diff)

## Artifact

```
## RISK MAP: [title]
1. [scenario] — P:[H/M/L] Cost:[H/M/L] Invisibility:[H/M/L] → mitigation, test, tripwire
**Clean zones:** [...]
**Spike required:** [unknown, experiment, result]
```

End with: "Risk map complete. Next: Implementer hat. Budget: deep care on items 1–2, speed everywhere else."
