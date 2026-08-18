# Issue 58 founder UAT (Slice D)

Perform this on persistent Railway UAT (`integration/agent`) or production after deploy.
Record: exact SHA, Alembic revision, feature flags, pass/fail per step.

Flags stay off unless the Founder turns `DISCOVERY_USEFULNESS_GOVERNOR_V1` on for a named UAT session.

## 12 steps (synthetic, no PHI)

1. Open a Case with the issue 58 fixture first turn: bilateral nighttime burning feet, no identity.
2. Continue through meal-delayed facial heat and right-upper discomfort.
3. Say “Let's not deal with the burning feet.” Confirm the Case still holds that concern as paused, not closed.
4. Say “There is a delay like I said. What do you think I should do? I don't have any more labs.”
4b. On a burning-feet Case, say “My last B12 check was last year. I want answers now. Is there any other insight?”
5. Confirm the reply is synthesis or next steps, not another laterality/B12/lab-upload question. Open `Why is this here?` and confirm the same family/candidate IDs as the chat extras.
6. Confirm three distinct concerns remain. No shared-cause or diagnosis language.
7. Confirm “inflammatory” stays patient attribution.
8. Confirm one to three ranked next-evidence options appear. EMG must not be offered as addressing small-fiber density.
9. Confirm any research cards resolve to stored sources. No invented PMID.
10. Replay the same last turn with the same idempotency key. No duplicate pause or decision event.
11. Say a paused-branch safety line such as “I suddenly cannot lift my foot.” Urgent language must still appear.
12. Sign the record: SHA, revision, flags, screenshots of pause + next steps, defects.

## API evidence

`tests/test_api/test_issue_58_uat.py` walks the fixture at the Case/turn API. It does not replace this browser sign-off.

## Rollback

Disable `DISCOVERY_USEFULNESS_GOVERNOR_V1`. Leave `control_json` in place. Old readers ignore it.
