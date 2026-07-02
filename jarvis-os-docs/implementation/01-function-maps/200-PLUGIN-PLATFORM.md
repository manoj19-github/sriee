# Function Map — Plugin Platform

Source: [plugin system](../../21-PLUGIN_SYSTEM.md) and [security model](../../19-SECURITY_MODEL.md).

Technology: signed manifests/packages, out-of-process host, schema-defined RPC, capability tokens.

| Global ID | Canonical name | Function | Description | Reads | Writes | Status | Notes |
|---|---|---|---|---|---|---|---|
| 200000 | `shared-plugin-validate-manifest-optional-p2-planned-current-v1` | `validatePluginManifest` | Validates identity, versions, entry point, schemas, permissions, network and uninstall declaration. | plugin manifest; host contracts | local: validation report | planned/current/v1 | Unknown mandatory fields/capabilities fail. |
| 200001 | `shared-plugin-verify-package-optional-p2-planned-current-v1` | `verifyPluginPackage` | Verifies publisher signature, integrity hashes, provenance and revocation status before extraction. | plugin package; trust/revocation store | local: verified package metadata | planned/current/v1 | Extraction defends traversal/symlink attacks. |
| 200002 | `csharp-plugin-preview-permissions-optional-p2-planned-current-v1` | `previewPluginPermissions` | Shows capability/resource/network/data access and version permission diff in trusted UI. | verified manifest; current grants | UI: install/update decision | planned/current/v1 | Install does not imply activation. |
| 200003 | `csharp-plugin-install-package-optional-p2-planned-current-v1` | `installPluginPackage` | Atomically installs verified package in isolated version directory and registers disabled state. | approved package; manifest | local/db: plugin installation | planned/current/v1 | Rollback retains prior compatible version. |
| 200004 | `csharp-plugin-start-host-optional-p2-planned-current-v1` | `startPluginHost` | Starts out-of-process plugin under job/token/resource/network restrictions and handshake. | installed package; grants | OS: restricted process; local session | planned/current/v1 | No in-process native plugin in initial SDK. |
| 200005 | `shared-plugin-issue-capability-token-optional-p2-planned-current-v1` | `issuePluginCapabilityToken` | Issues short-lived audience-bound token for exact approved capability/resource. | plugin identity; grant; task context | local: capability token/audit | planned/current/v1 | Plugin cannot delegate or broaden token. |
| 200006 | `shared-plugin-invoke-function-optional-p2-planned-current-v1` | `invokePluginFunction` | Validates schema/token/deadline, invokes RPC and validates/redacts response. | function request; token; schemas | plugin RPC; task observation/result | planned/current/v1 | Plugin output is untrusted data. |
| 200007 | `shared-plugin-monitor-health-optional-p2-planned-current-v1` | `monitorPluginHealth` | Tracks startup, crashes, timeout, quota and circuit-breaker state. | plugin host telemetry | local/db: health state | planned/current/v1 | Repeated failure disables plugin safely. |
| 200008 | `shared-plugin-update-package-optional-p2-planned-current-v1` | `updatePluginPackage` | Verifies new version, displays permission diff, migrates plugin-owned data and health-checks. | installed/new package; user decision | local/db: active plugin version | planned/current/v1 | New permission always requires approval. |
| 200009 | `shared-plugin-revoke-disable-optional-p2-planned-current-v1` | `revokeOrDisablePlugin` | Revokes tokens, stops host, rejects new calls and records reason. | revocation/security/user request | local/db: disabled/revoked state | planned/current/v1 | Emergency revocation can be immediate. |
| 200010 | `shared-plugin-uninstall-package-optional-p2-planned-current-v1` | `uninstallPluginPackage` | Stops/revokes, removes binaries and offers explicit plugin-data retain/export/delete choice. | installation/data inventory; user choice | filesystem/db: removal/deletion receipt | planned/current/v1 | Never deletes external user project data. |

## Change rule

Update this map and plugin threat model before changing manifest, trust/signature, sandbox, RPC, capability token, update, revocation, or uninstall behavior.
