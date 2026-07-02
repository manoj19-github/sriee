# Voice System

## Pipeline

Microphone → local wake word → visible capture session → voice activity detection → speech-to-text → transcript confirmation when consequential → task API → response text → text-to-speech.

Wake-word audio uses a short in-memory ring buffer and is not persisted. Recording state MUST be unmistakable in the window and tray. Push-to-talk is always available. A global stop control immediately ends capture and playback.

## Commands and risk

Voice identity is not sufficient authorization for high-risk actions. The desktop shows the same action-bound approval card used for text requests; configurable voice confirmation may supplement but never replace Windows session/user validation.

## Failure behavior

Low-confidence transcripts are clarified. Names, paths, amounts, recipients, destructive verbs, and commands require extra confidence or visual confirmation. Network STT failure falls back locally when configured. Raw audio retention is off by default.

## Testing

Measure wake false accepts/rejects, transcription word error rate across supported accents/noise, end-of-speech latency, cancellation latency, device switching, accessibility, and accidental activation during TTS.
