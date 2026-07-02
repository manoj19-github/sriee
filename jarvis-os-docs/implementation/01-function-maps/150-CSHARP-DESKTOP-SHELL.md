# Function Map — C# Desktop Shell

Source: [C# desktop architecture](../../24-C_SHARP_DESKTOP.md), [service blueprint](../../05-SERVICE_BLUEPRINT.md), and [permission system](../../20-PERMISSION_SYSTEM.md).

Technology: supported .NET LTS, WPF, MVVM, dependency injection, generated contracts.

| Global ID | Canonical name | Function | Description | Reads | Writes | Status | Notes |
|---|---|---|---|---|---|---|---|
| 150000 | `csharp-desktop-start-application-mandatory-p0-planned-current-v1` | `startDesktopApplication` | Loads safe configuration, single-instance coordination, DI, telemetry and main window/tray.<br>Shows actionable startup failure without exposing secrets. | local settings; OS session | process/UI: desktop lifecycle | planned/current/v1 | Runs unelevated. |
| 150001 | `csharp-desktop-connect-backend-mandatory-p0-planned-current-v1` | `connectBackend` | Establishes authenticated REST/WebSocket session, negotiates contracts and reconnects with jitter. | local device identity; backend endpoint | local: connection state; ws session | planned/current/v1 | Resyncs durable events after reconnect. |
| 150002 | `csharp-desktop-submit-request-mandatory-p0-planned-current-v1` | `submitTaskRequest` | Sends text/transcript with idempotency and correlation IDs, then opens task timeline. | UI input; current context selection | api: task request; UI: task view | planned/current/v1 | Empty/oversized input rejected locally and server-side. |
| 150003 | `csharp-desktop-render-task-timeline-mandatory-p0-planned-current-v1` | `renderTaskTimeline` | Projects ordered task events into accessible status, plan, approval, action and result cards. | ws/REST: task events | UI: task projection | planned/current/v1 | Duplicate events are harmless; gaps trigger resync. |
| 150004 | `csharp-desktop-render-plan-preview-mandatory-p0-planned-current-v1` | `renderPlanPreview` | Displays dependencies, exact targets, risk, verification and rollback before mutation. | task plan/policy decisions | UI only | planned/current/v1 | Raw model prose is never rendered as executable action. |
| 150005 | `csharp-desktop-present-approval-mandatory-p0-planned-current-v1` | `presentApprovalCard` | Uses trusted native surface for exact action-bound approve/deny decision with countdown/expiry. | pending approval/action digest | api/local: approval decision | planned/current/v1 | Delegates cryptographic checks to security module. |
| 150006 | `csharp-desktop-cancel-task-mandatory-p0-planned-current-v1` | `cancelActiveTask` | Sends cancellation and immediately signals owned local execution while displaying reconciliation state. | UI cancel; active task/action | api: cancel; executor: cancellation token | planned/current/v1 | Does not claim stopped until receipt/postcondition confirms. |
| 150007 | `csharp-desktop-manage-projects-mandatory-p0-planned-current-v1` | `manageProjectRegistry` | Registers canonical project path, runbook, expected services and allowed tools through validated UI. | user input; filesystem observations | api/db: project configuration | planned/current/v1 | Paths are re-canonicalized by executor. |
| 150008 | `csharp-desktop-manage-permissions-mandatory-p1-planned-current-v1` | `managePermissionCenter` | Lists effective policy/grants, explains use and supports eligible revocation/narrowing. | local policy/grants/audit summaries | local/api: grant changes | planned/current/v1 | Cannot weaken non-overridable baseline. |
| 150009 | `csharp-desktop-manage-memory-privacy-mandatory-p1-planned-current-v1` | `managePrivacyCenter` | Shows memory/artifact retention, export/deletion and voice/screen settings. | api: memories/artifacts; local privacy settings | api/local: consent/deletion/settings | planned/current/v1 | Personal content hidden from diagnostics by default. |
| 150010 | `csharp-desktop-show-notification-mandatory-p1-planned-current-v1` | `showTaskNotification` | Displays completion, approval or failure notification with privacy-aware preview. | task event; privacy setting | OS: toast notification | planned/current/v1 | No secret/path/content preview on lock screen. |
| 150011 | `csharp-desktop-export-diagnostics-mandatory-p1-planned-current-v1` | `exportDiagnosticBundle` | Builds user-reviewed redacted bundle of versions, IDs, transitions and errors. | local/backend telemetry; redaction policy | local: selected archive | planned/current/v1 | Raw prompts, credentials and personal artifacts excluded. |

## Change rule

Update this map before changing UI flows, event projections, approval presentation, connection behavior, privacy controls, or accessibility behavior.
