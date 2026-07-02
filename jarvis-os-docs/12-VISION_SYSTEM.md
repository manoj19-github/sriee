# Vision System

Vision is request-scoped by default. Screen capture, OCR, and optional camera features are separate capabilities with separate indicators and grants.

## Screen path

Desktop captures an allowed monitor/window → redacts configured regions → attaches classification and expiry → backend/model produces structured observations → verifier may use observations as evidence.

Prefer Windows UI Automation/accessibility trees over pixels. Use OCR when structured APIs are unavailable. Coordinate-based clicks are last-resort, previewed, and invalidated if layout changes.

## Safety and privacy

Never capture password fields, secure desktop, DRM-protected content, or excluded applications. Camera analysis cannot infer emotion, intent, honesty, health diagnosis, or protected traits. Face recognition is out of scope. Screenshots are sensitive, encrypted, short-lived, and excluded from training.

## Quality

Record capture source, scale, bounds, OCR/model version, confidence, and redactions. Test multiple DPI settings, monitors, themes, minimized/occluded windows, sensitive overlays, and prompt injection rendered on screen.
