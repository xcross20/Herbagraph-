# Founder UAT script (PR-54)

Perform this on persistent Railway UAT (`integration/agent`) without database access.

Record: exact UAT SHA, Alembic revision, feature flags, pass/fail per step.

## 19 steps

1. Sign in with a seeded UAT account.
2. Open a Case: “For six months my feet have burned at night. Blood work was normal.”
3. Confirm the reply is an investigation, not a diagnosis.
4. Attach a normal EMG report.
5. Open the investigation map. Small-fiber remains open. EMG does not close it.
6. Ask a follow-up. History is still there after the new turn.
7. Replay the same turn. One semantic effect.
8. Correct onset A→B→A. Inactive history remains.
9. Upload an unreadable file. Outcome is not success.
10. Upload or mention a lab CSV. It routes to the lab engine, not a fake Discovery parse.
11. Record monitoring: no change, unknown adherence. No causal claim appears.
12. Open a chest-pain Case. Urgent language appears and survives a follow-up.
13. Open a gallbladder Case and attach EMG. No biliary evidence is created.
14. Log in as a second user. The first Case is not visible.
15. Keyboard through the Case view. Focus and labels remain usable.
16. Narrow the viewport. The core journey still works.
17. Close the browser, sign in again, reopen the Case. State is the same.
18. Confirm no “you have” / disease-probability copy.
19. Sign the record: SHA, revision, flags, defects, pass/fail.

## Evidence to capture

- Screenshots of map, safety, and correction history
- Network log without PHI
- Exact deployment SHA and `alembic current`

This API suite is `tests/test_api/test_founder_uat_scenario.py`. It does **not** replace Founder browser sign-off.
