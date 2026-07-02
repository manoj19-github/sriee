# Desktop Automation

## Adapter order

1. Stable application API/CLI.
2. Windows UI Automation.
3. Documented Win32/COM API.
4. Simulated keyboard/mouse only with foreground validation and user-visible preview.

## Executor pipeline

Receive `ActionRequest` → authenticate backend → validate schema/version → resolve registered capability → canonicalize resources → evaluate local policy → validate approval digest → acquire resource lease → reconcile idempotency → execute with timeout → capture receipt → verify postcondition → emit `ActionResult`.

## Initial capabilities

- `app.open`, `app.close`
- `window.list`, `window.focus`, `window.move_resize`
- `clipboard.read`, `clipboard.write`
- `project.inspect`, `file.read_scoped`, `file.patch_scoped`
- `process.list`, `process.start_registered`, `process.stop_owned`
- `notification.show`
- `screen.capture_window`

Shutdown, restart, registry, services, software installation, device control, and elevation remain disabled until separately threat-modeled.

## Rules

Canonical paths MUST stay inside granted roots. Executables resolve from a signed registry, not model text. Arguments are arrays, never concatenated shell strings. Process trees are job-scoped and cancellable. Each adapter returns typed domain errors and a verifiable receipt.
