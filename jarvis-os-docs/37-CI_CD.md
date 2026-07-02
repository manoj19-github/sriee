# CI/CD

## Pull request pipeline

Change classification → secret/license scan → formatting/lint/type checks → Python/.NET unit tests → contract generation/diff → graph/evaluation smoke → integration tests → build/package → SBOM and vulnerability scan → artifact retention.

Path filters may skip irrelevant expensive suites, but contract, policy, executor, and shared dependency changes trigger both Python and C# tests. Untrusted fork builds receive no secrets or signing access.

## Release pipeline

Protected tag → clean reproducible build → full Windows VM/E2E/safety suite → migration rehearsal → sign assemblies/MSIX/bundles → generate SBOM/provenance/checksums → publish preview ring → health/rollback gate → staged stable rollout.

## Supply chain

Pin dependencies and actions by immutable version/digest, minimize CI permissions, use ephemeral runners for signing, protect keys in hardware/managed signing service, verify provenance during update, and support emergency revocation.

Deployment cannot automatically widen permissions or remembered grants.
