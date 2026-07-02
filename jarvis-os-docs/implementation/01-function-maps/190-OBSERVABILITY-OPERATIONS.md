# Function Map — Observability and Operations

Source: [monitoring](../../39-MONITORING.md), [CI/CD](../../37-CI_CD.md), and [deployment](../../38-DEPLOYMENT.md).

Technology: OpenTelemetry, structured logs, signed builds/MSIX, SBOM/provenance, staged release.

| Global ID | Canonical name | Function | Description | Reads | Writes | Status | Notes |
|---|---|---|---|---|---|---|---|
| 190000 | `shared-observability-create-correlation-mandatory-p0-planned-current-v1` | `createCorrelationContext` | Creates/propagates trace, task, action and attempt IDs across processes and events. | inbound headers/message | logs/traces/events: IDs | planned/current/v1 | IDs contain no personal meaning. |
| 190001 | `shared-observability-write-structured-log-mandatory-p0-planned-current-v1` | `writeStructuredLog` | Emits schema-versioned event with severity/code/safe fields after redaction. | application event; redaction rules | local/collector: log record | planned/current/v1 | No raw prompts, command output or secrets by default. |
| 190002 | `shared-observability-record-trace-mandatory-p1-planned-current-v1` | `recordDistributedTrace` | Traces API, graph node, policy, approval, dispatch, execution and verification spans. | correlation context; timings | OTel collector/exporter | planned/current/v1 | Optional export; local inspectable. |
| 190003 | `shared-observability-record-metrics-mandatory-p1-planned-current-v1` | `recordOperationalMetrics` | Records bounded-cardinality task, action, policy, model, socket and resource metrics. | runtime measurements | OTel metrics store | planned/current/v1 | Never label with raw user/path/task content. |
| 190004 | `shared-operations-run-health-check-mandatory-p0-planned-current-v1` | `runDependencyHealthChecks` | Checks local backend, DB, checkpointer, desktop and optional providers with degraded states. | runtime dependencies | health projection/metrics | planned/current/v1 | Health checks are bounded and non-destructive. |
| 190005 | `shared-operations-build-diagnostic-bundle-mandatory-p1-planned-current-v1` | `buildRedactedDiagnosticBundle` | Collects versions, transitions, safe errors and configuration fingerprints for user review. | logs/traces/version manifests | selected local archive | planned/current/v1 | Seeded-secret scan before completion. |
| 190006 | `ci-quality-validate-contracts-mandatory-p0-planned-current-v1` | `validateCrossLanguageContracts` | Generates/validates schemas and golden fixtures in Python/C#; detects breaking diffs. | contract sources/fixtures | CI report/generated code | planned/current/v1 | Required on every contract change. |
| 190007 | `ci-quality-run-safety-suite-mandatory-p0-planned-current-v1` | `runSafetyEvaluationSuite` | Exercises deny/ask/allow, injection, path, replay, cancellation and secret-leak scenarios. | test builds; golden datasets | CI evaluation report | planned/current/v1 | Zero unapproved R3/R4 execution release gate. |
| 190008 | `ci-release-build-artifacts-mandatory-p1-planned-current-v1` | `buildReleaseArtifacts` | Reproducibly builds backend/desktop, generates checksums, SBOM and provenance. | tagged source; locked dependencies | CI artifact store | planned/current/v1 | Untrusted builds get no signing credentials. |
| 190009 | `ci-release-sign-artifacts-mandatory-p1-planned-current-v1` | `signReleaseArtifacts` | Signs approved artifacts/manifests through protected signing identity. | release artifacts; protected key service | signed packages/manifests | planned/current/v1 | Hardware/managed key, auditable use. |
| 190010 | `csharp-update-apply-signed-release-mandatory-p1-planned-current-v1` | `applySignedUpdate` | Verifies signature/hash/channel, previews material changes, quiesces tasks, migrates and health-checks. | signed manifest/package; current tasks | local install/data version | planned/current/v1 | Does not widen grants; rollback package retained. |
| 190011 | `shared-operations-backup-restore-data-mandatory-p1-planned-current-v1` | `backupAndRestoreData` | Produces encrypted schema/artifact backup and rehearses verified restore. | DB/artifact store; key policy | backup store; restore evidence | planned/current/v1 | Credentials and unrelated DB schemas excluded. |

## Change rule

Update this map before changing telemetry fields, exporters, health semantics, diagnostics, build/sign/update, backup, or release gates.
