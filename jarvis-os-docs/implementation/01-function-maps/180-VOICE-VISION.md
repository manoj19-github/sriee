# Function Map — Voice and Vision

Source: [voice system](../../11-VOICE_SYSTEM.md) and [vision system](../../12-VISION_SYSTEM.md).

Technology: local wake word/VAD, provider-neutral STT/TTS, Windows UI Automation, request-scoped capture, OCR/vision gateway.

| Global ID | Canonical name | Function | Description | Reads | Writes | Status | Notes |
|---|---|---|---|---|---|---|---|
| 180000 | `csharp-voice-select-device-optional-p2-planned-current-v1` | `selectAudioDevice` | Lists and selects available microphone/speaker with privacy-aware test controls. | OS audio devices; user setting | local: audio preference | planned/current/v1 | Voice remains opt-in; text always available. |
| 180001 | `csharp-voice-detect-wake-word-optional-p2-planned-current-v1` | `detectWakeWord` | Runs local wake detector over short in-memory ring buffer and starts visible capture session. | microphone ring buffer; local model | local/UI: capture session | planned/current/v1 | Buffer not persisted; kill control immediate. |
| 180002 | `csharp-voice-capture-utterance-optional-p2-planned-current-v1` | `captureUtterance` | Captures until VAD/end/cancel with visible indicator and strict duration/size limits. | microphone; capture controls | memory/temp: encrypted audio artifact | planned/current/v1 | Raw retention off by default. |
| 180003 | `python-voice-transcribe-speech-optional-p2-planned-current-v1` | `transcribeSpeech` | Converts permitted audio to transcript with language, word confidence and uncertain spans. | audio artifact; STT provider policy | graph: transcript; ephemeral metadata | planned/current/v1 | Cloud egress requires configured consent/data class. |
| 180004 | `python-voice-confirm-consequential-text-optional-p2-planned-current-v1` | `confirmConsequentialTranscript` | Requires visual confirmation when low-confidence names, paths, recipients, amounts or destructive terms affect action. | transcript/confidence; intent risk | UI: confirmation request | planned/current/v1 | Voice identity never replaces R3 approval. |
| 180005 | `csharp-voice-speak-response-optional-p2-planned-current-v1` | `speakResponse` | Speaks privacy-filtered result and stops instantly on user input/cancel. | final response; privacy/audio settings | OS audio output | planned/current/v1 | Prevent wake detector feedback loop. |
| 180006 | `csharp-vision-read-ui-automation-optional-p1-planned-current-v1` | `readUiAutomationTree` | Reads semantic accessible elements from explicitly scoped window. | OS UIA tree; window grant | graph: bounded structured observation | planned/current/v1 | Preferred over screenshot and coordinate actions. |
| 180007 | `csharp-vision-capture-window-optional-p2-planned-current-v1` | `capturePermittedWindow` | Captures exact allowed window/monitor after excluded-app/secure-field checks and redaction. | OS screen/window; privacy exclusions | encrypted short-lived artifact | planned/current/v1 | Secure desktop and protected content denied. |
| 180008 | `python-vision-extract-screen-text-optional-p2-planned-current-v1` | `extractScreenText` | OCRs permitted capture and returns text/bounds/confidence with provenance. | screenshot artifact; OCR model | graph: OCR observations | planned/current/v1 | Visible instructions remain untrusted data. |
| 180009 | `python-vision-describe-screen-optional-p2-planned-current-v1` | `describeScreenContext` | Produces task-relevant observable description without identity/emotion/intent inference. | permitted image/UIA observations; vision model | graph: cited observations | planned/current/v1 | Uncertainty and occlusion surfaced. |
| 180010 | `csharp-vision-expire-artifact-mandatory-p1-planned-current-v1` | `expireCaptureArtifact` | Deletes temporary audio/screen artifacts and index references at session/retention expiry. | artifact metadata; retention policy | artifact store/db: deletion receipt | planned/current/v1 | Retry and user-visible deletion status. |

## Change rule

Update this map and privacy review before changing recording/capture activation, retention, indicators, provider egress, OCR, camera, or inference behavior.
