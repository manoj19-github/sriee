# Stage 07 — Hardening, Plugins, Packaging, and Release

## Dependencies

All intended release features have passed their component gates. Optional unfinished components remain disabled.

## Functions

190000–190011, 200000–200010, and release-ready verification of every shipped Global ID.

## Steps

1. Finalize structured logs, traces, bounded metrics and user-controlled telemetry.
2. Add redacted diagnostic bundle and seeded-secret gate.
3. Run performance/resource profiling, soak, chaos/restart and queue backpressure tests.
4. Complete keyboard, screen-reader, contrast, scaling and reduced-motion audit.
5. Generate SBOM/provenance, scan dependencies/licenses and remediate release findings.
6. Rehearse `jarvis` schema backup, migration, failed migration and restore.
7. Build reproducible backend/desktop artifacts and signed MSIX/update manifest.
8. Test install, upgrade, rollback and uninstall with retain/export/delete choices.
9. If plugins ship, complete out-of-process host, signature, permissions, quotas, revocation and sample plugin.
10. Execute full safety evaluation and threat-model review.
11. Publish preview ring, observe SLO/error/security gates, then staged stable rollout.
12. Freeze release record with every contract, prompt, policy, migration and model version.

## Release blockers

Any unapproved R3/R4 action; secret leakage; unsigned/unverifiable artifact; migration without restore; critical/high exploitable finding; contract incompatibility; missing cancellation/restart safety; inaccessible approval flow; misleading success report.

## Exit gate

Signed release passes the release checklist in a clean Windows VM, rollback/restore drills succeed, every shipped function has test evidence and current status, and disabled functions are absent from the advertised capability manifest.
