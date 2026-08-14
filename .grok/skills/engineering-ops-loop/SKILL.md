---
name: engineering-ops-loop
description: >
  The Loop — autonomous implement/test/fix cycle. Combines Implementer and
  QA hats. Highest-priority rule: a failing test is information about the
  CODE, never a reason to weaken the test. Use when the user runs
  /engineering-ops-loop, /loop, or "keep going until tests pass."
metadata:
  short-description: "Implement/test/fix loop; never weaken tests"
---

# The Loop

Read `../engineering-operating-manual/references/9-loop.agent.md`.

You are Implementer + QA in one cycle: write → run tests → read the failure → fix → re-run.

## THE RULE THAT OUTRANKS THIS FILE

**A test failing is information about the CODE, not a problem with the TEST.**

Legitimate moves only:

1. Fix the implementation so it satisfies the test as originally written.
2. If you believe the test is wrong, STOP. Do not touch the test file. Report which assertion and why.

Never weaken, skip, delete, or swallow a failing test to get green. The shortest path to green is almost always cheating the test.

## Loop

1. Implement the current slice.
2. Run the real test command (`pytest`, `bash scripts/ci_gates.sh` on HerbaGraph).
3. Read the actual failure output.
4. Diagnose. Default: the code is wrong.
5. Smallest fix for the diagnosed cause.
6. Re-run.

Stop if: all tests pass and you can map each to an acceptance claim; **5 attempts on the same failure**; the test looks wrong; a one-way door appears that the design did not open.

End: "Loop complete: [N] attempts, [pass/capped]. Next: Reviewer hat — take a context break first."
