# ADR 0007 — Agent-loop bootstrap and rollback

## Status

Proposed. Not activated. `agent-loop` stays off until founder-approved installation on protected `main`.

## Decision

`pull_request_target` loads workflow YAML from the repository default branch (`main`), not from `integration/agent` or the PR head. A no-secret qualify job resolves the default-branch SHA once and verifies `.github/agent-loop.lock`. An empty lock is not approval. A populated lock must match the resolved SHA or a GitHub-compare descendant. Every trusted job checks out that exact resolved SHA. The review artifact is bound to it.

A canary may start only after:

1. `main` and `integration/agent` require PRs and CI.
2. This workflow file is merged to protected `main` by a founder-approved promotion PR.
3. Model secrets exist as repository secrets (`OPENAI_API_KEY`, `XAI_API_KEY`) and are never created by the loop.

Trust domains are separate jobs:

- secret-bearing model jobs execute no PR code and do not receive write tokens
- a no-secrets job validates patches and tests
- a fresh job performs the GitHub-API commit and exact-SHA fast-forward

## Rollback

1. Remove the `agent-loop` label from any open PR (loop will not qualify).
2. Revert this workflow on `main` with a founder PR.
3. Rotate `OPENAI_API_KEY` and `XAI_API_KEY` if a secret-bearing job was compromised.
4. Do not force-push `main` or `integration/agent`.

## Consequences

The loop cannot run until the founder installs it on `main`. That is intentional. Temporary PR previews and persistent UAT test the application; this protocol is tested in GitHub.
