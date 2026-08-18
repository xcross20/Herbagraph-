# Discovery MVP threat model

Reviewed surfaces for PR-52. Founder still owns independent security review.

## Assets

- Longitudinal Cases, findings, documents, maps, monitoring events
- Auth tokens and UAT/production secrets
- Uploaded reports (may contain PHI)

## Threats and controls

| Threat | Control |
|---|---|
| IDOR on Case and nested resources | Central `require_owned_case`; 404 on miss; tests for substitution |
| Role escalation | Verified-user dependency; clinician/admin role does not bypass owner scope on Cases |
| Prompt injection in uploads | Document classifier does not grant system authority; findings go through mutation seam |
| Malicious/oversized upload | Type/outcome classification; unsupported/failed outcomes do not persist success |
| Cross-tenant cache leakage | No shared in-memory Case cache keyed without user id |
| SSRF via document URL | Document API accepts uploaded text, not remote fetch |
| Secret leakage | UAT and production remain separate Railway projects |
| Model-provider data | Literature retrieval uses query fragments, not full charts |
| PHI in logs/metrics | Telemetry counters reject PHI-like keys; audit summaries are resource ids only |

## Residual risk

- GitHub Actions billing currently blocks independent CI proof of the security suite.
- Malware scanning of binaries is a boundary, not implemented as a scanner.
- Signed object-storage URLs are not used for Discovery text uploads.
