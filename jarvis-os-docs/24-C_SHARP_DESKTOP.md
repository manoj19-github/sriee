# C# Windows Desktop

## Solution

- `Jarvis.Desktop`: WPF shell, MVVM, accessibility, tray.
- `Jarvis.Contracts`: generated/versioned transport types.
- `Jarvis.Core`: task/session abstractions and policy interfaces.
- `Jarvis.Executor`: validation, leases, receipts, adapter dispatch.
- `Jarvis.Windows`: Win32/UIA/process/window implementations.
- `Jarvis.Security`: identity, approvals, signing, secret handles.
- `Jarvis.Telemetry`: structured logging and OpenTelemetry.
- `Jarvis.Tests.*`: unit, contract, integration, Windows VM tests.

## UI surfaces

Command bar, task timeline, plan preview, native approval dialog, project registry, permission center, memory/privacy center, diagnostics, and update status.

## Engineering rules

Async work accepts `CancellationToken`; UI thread never blocks. Native handles are wrapped in `SafeHandle`. P/Invoke is centralized and reviewed. Nullable reference types and analyzers are enabled. Dependency injection scopes adapters. Exceptions become typed results at transport boundaries.

The app runs unelevated. A future elevation broker, if justified, is a separate signed process with narrow commands and fresh consent—not a permanently elevated desktop app.
