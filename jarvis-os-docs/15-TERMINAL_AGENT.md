# Terminal Agent

The terminal agent proposes a `ProcessSpec`; it never emits a free-form command for implicit execution.

```json
{
  "executable_id": "dotnet",
  "arguments": ["test", "--no-restore"],
  "working_directory_ref": "project:api",
  "environment_refs": [],
  "timeout_seconds": 600,
  "network": "deny",
  "output_limit_bytes": 2000000
}
```

The desktop resolves executable IDs, canonicalizes the working directory, validates each argument, strips unsafe environment variables, applies resource/time limits, and captures stdout/stderr separately. Shells (`cmd`, PowerShell, WSL) are distinct high-risk capabilities and are not a shortcut around argument validation.

Interactive prompts fail unless the action explicitly declares an interactive desktop session. Secret values use out-of-band handles and are redacted. Cancellation terminates the owned process tree. Success requires exit code plus command-specific verification.
