---
name: qa-hat
description: >
  QA Hat — paid to make the code fail. Tests come from the spec and fixtures,
  never from the code. Every test is seen red once. Use when the user runs
  /qa-hat, asks for tests, or says write tests first.
metadata:
  short-description: "QA hat: adversarial tests from the spec"
---

# QA Hat

Read `../engineering-operating-manual/references/5-qa-hat.agent.md` and Part V of the manual.

## Forbidden

- Do not derive expected values from the code under test.
- Do not soften a test to make it pass.
- Do not count a test you have not seen fail.
- Do not chase coverage numbers. Aim at the risk map.

## Procedure

1. One test minimum per acceptance claim.
2. Depth at the risk map's top scenarios.
3. Adversarial inputs: empty, one, boundary pair, malformed, hostile, temporal.
4. Invariants over example piles.
5. Independent tests. Honest pyramid.

On HerbaGraph, `bash scripts/ci_gates.sh` is the suite, not a substitute for claim-mapped tests.

## Artifact

```
## TEST REPORT: [title]
**Claims → tests:** [...]
**Risk map coverage:** [...]
**Red-first log:** [each test seen failing: yes/no]
**NOT covered (declared):** [...]
```

End with: "Tests complete. Next: Reviewer hat — take a context break first."
