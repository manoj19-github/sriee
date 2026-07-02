# Vision System

Vision is request-scoped by default. Screen capture, OCR, and optional camera features are separate capabilities with separate indicators and grants.

## Screen path

Desktop captures an allowed monitor/window → redacts configured regions → attaches classification and expiry → backend/model produces structured observations → verifier may use observations as evidence.

Prefer Windows UI Automation/accessibility trees over pixels. Use OCR when structured APIs are unavailable. Coordinate-based clicks are last-resort, previewed, and invalidated if layout changes.

## Optional camera path

Trusted visible camera session → local person-presence observation → optional local enrolled-face match → optional visible-expression cue → bounded companion context → frame expiry.

Ambient presence mode requires a separate explicit grant, trusted window/tray indicator, short in-memory buffering, quiet/private modes, greeting cooldown and immediate kill control. The hardware shutter, OS privacy denial, lock screen, secure desktop and revocation always take precedence.

Face enrollment is optional biometric processing. It creates an encrypted local template after explicit consent and liveness checks; raw enrollment images are deleted and cloud egress is disabled by default. Matching supports personalization only. Unknown and low-confidence results abstain, and a match never unlocks the device or authorizes a consequential action.

Expression processing is limited to tentative visible cues such as a possible smile or yawn. Dialogue must use uncertain wording and invite correction—for example, “You seem to be smiling; did something nice happen?” It cannot assert happiness, sadness, stress, illness, honesty or intent.

## Safety and privacy

Never capture password fields, secure desktop, DRM-protected content, or excluded applications. Camera analysis cannot claim emotion, intent, honesty, health diagnosis, or protected traits. General face identification is out of scope; only explicit local enrolled-user matching is planned. Screenshots, camera frames and biometric templates are sensitive, encrypted where persisted, excluded from training, and governed by separate retention/deletion rules.

## Quality

Record capture source, scale, bounds, OCR/model version, confidence, and redactions without logging raw personal content. Test multiple DPI settings, monitors, themes, minimized/occluded windows, sensitive overlays, prompt injection rendered on screen, camera denial/disconnect, spoof/liveness cases, varied lighting, false matches, abstention, deletion and immediate sensor shutdown.
