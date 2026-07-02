# Function Map — Security and Policy

Source: [security model](../../19-SECURITY_MODEL.md) and [permission system](../../20-PERMISSION_SYSTEM.md).

Technology: deterministic policy engine, Windows identity/credential protection, cryptographic action digests, append-only audit.

| Global ID | Canonical name | Function | Description | Reads | Writes | Status | Notes |
|---|---|---|---|---|---|---|---|
| 130000 | `shared-security-register-device-mandatory-p0-planned-current-v1` | `registerDeviceIdentity` | Creates per-install device identity and binds it to the interactive user after explicit setup. | OS user/session; local key store | local/db: device public identity | planned/current/v1 | Private material is non-exportable where platform supports it. |
| 130001 | `shared-security-authenticate-session-mandatory-p0-planned-current-v1` | `authenticateSession` | Establishes short-lived mutually bound desktop/backend session and prevents loopback impersonation. | device proof; nonce; user session | local/db: session metadata | planned/current/v1 | Includes replay protection and rotation. |
| 130002 | `csharp-policy-load-baseline-mandatory-p0-planned-current-v1` | `loadPolicyBaseline` | Loads signed deny-by-default local policy and rejects invalid/unknown policy versions. | packaged policy; admin/user overlays | memory: effective policy | planned/current/v1 | Model and backend cannot replace local baseline. |
| 130003 | `csharp-policy-evaluate-action-mandatory-p0-planned-current-v1` | `evaluateActionPolicy` | Computes allow/ask/deny from actor, device, capability, canonical resource, parameters and context. | action; effective policy; grants | local: policy decision; audit | planned/current/v1 | Re-evaluated immediately before execution. |
| 130004 | `shared-security-calculate-action-digest-mandatory-p0-planned-current-v1` | `calculateActionDigest` | Canonically serializes security-relevant action fields and computes versioned digest. | action request; digest algorithm version | action/approval: digest | planned/current/v1 | Any material parameter change invalidates approval. |
| 130005 | `csharp-security-show-approval-mandatory-p0-planned-current-v1` | `showNativeApproval` | Displays exact target, effect, risk, expiry and rollback in trusted native UI and captures decision. | action preview; policy decision; OS session | local/api: signed approval decision | planned/current/v1 | R3 cannot use blanket approval. |
| 130006 | `csharp-security-validate-approval-mandatory-p0-planned-current-v1` | `validateApproval` | Validates actor/device, action digest, nonce, signature, policy version, expiry and unused state. | pending action; approval; current policy | local/db: consumed approval/audit | planned/current/v1 | Fail closed on clock uncertainty or mismatch. |
| 130007 | `shared-security-manage-grant-mandatory-p1-planned-current-v1` | `manageCapabilityGrant` | Creates, lists, narrows, expires and revokes eligible R1/R2 scoped grants through trusted UI. | user decision; capability/resource | local/db: capability grant | planned/current/v1 | Model cannot create or broaden grants. |
| 130008 | `shared-security-resolve-secret-handle-mandatory-p0-planned-current-v1` | `resolveSecretHandle` | Resolves opaque secret reference only inside an authorized adapter and redacts derived output. | OS credential store/vault; authorized handle | process/API call only | planned/current/v1 | Secret never enters graph state, model prompt or logs. |
| 130009 | `shared-security-redact-telemetry-mandatory-p0-planned-current-v1` | `redactTelemetry` | Classifies and removes secrets/personal payloads before logs, traces, bundles or model egress. | structured telemetry/artifact metadata | sanitized telemetry; redaction metrics | planned/current/v1 | Seeded-secret tests block release. |
| 130010 | `shared-security-append-audit-record-mandatory-p0-planned-current-v1` | `appendAuditRecord` | Appends correlation-linked decision/action/approval/result record with integrity chain. | security/domain event | local/db: audit record | planned/current/v1 | Payload is minimized; audit itself is access-controlled. |
| 130011 | `shared-security-revoke-device-mandatory-p1-planned-current-v1` | `revokeDevice` | Invalidates sessions, grants, plugin tokens and pending approvals for a device. | revocation request; device registry | db/local: revocation state/event | planned/current/v1 | Offline desktop enforces cached revocation expiry policy. |

## Change rule

Update this map and add a security deep dive before changing trust boundaries, risk tiers, approval fields, digest rules, key storage, grants, secret flow, or audit integrity.
