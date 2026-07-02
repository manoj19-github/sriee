# Stage 06 — Memory, RAG, Voice, and Vision

## Dependencies

Core task safety and privacy center are stable. Each feature launches independently behind opt-in flags.

## Functions

140006–140013 and 180000–180010.

## Steps

1. Implement memory candidate rules, prohibited-data filter and consent UI.
2. Add scoped memory retrieval with source, confidence, expiry and correction/deletion.
3. Add artifact classification, encryption, retention and deletion receipts.
4. Implement document source registration, parsing, checksum, ACL metadata and indexing.
5. Add filter-before-search retrieval, citations and injection-resistant context delimiters.
6. Implement UI Automation observation before any screenshot feature.
7. Add request-scoped window capture, exclusion/redaction and automatic expiry.
8. Add OCR/vision observations with provenance and forbidden-inference tests.
9. Add push-to-talk, visible audio session, local-first STT and transcript confirmation.
10. Add wake word only after false-activation/privacy evaluation.
11. Add TTS with interruption and wake-feedback suppression.

## Required tests

Cross-user/project ACL leakage, stale/deleted memory, secret candidate, malicious document/screen instructions, password field capture, excluded app, secure desktop, multi-monitor DPI, raw artifact expiry, cloud egress disabled, wake false accept, uncertain destructive transcript and immediate kill control.

## Exit gate

Users can see, correct and delete retained context; all captures are visible and scoped; no retrieved/visible instruction changes policy; prohibited inference and data leakage suites pass.
