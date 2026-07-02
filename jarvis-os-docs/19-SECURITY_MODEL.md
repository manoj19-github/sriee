# Security Model

## Protected assets

User files, credentials, personal memory, wellness/medication/mood records, audio/screens, source code, signing keys, device identity, approvals, audit integrity, and OS availability.

## Principal threats

Prompt injection from web/files/screens; malicious plugins; confused-deputy actions; path traversal; command injection; forged/replayed approvals; local socket hijacking; secret leakage to models/logs; dependency compromise; privilege escalation; denial of service; unsafe retries.

## Controls

- Model output is untrusted structured input.
- Executor policy is deterministic, local, deny-by-default, and signed/versioned.
- Loopback authentication plus per-install device identity; TLS outside loopback.
- Action-bound, expiring, single-use approvals with digest and nonce.
- Capability-scoped adapters, path canonicalization, argument arrays, job/process limits.
- Signed releases/plugins, SBOM, dependency scanning, and protected update channel.
- Encryption in transit/at rest; secrets by opaque handle.
- Tamper-evident audit chain with redacted fields.
- Egress allowlists and data-class policy.
- Rate, recursion, token, cost, CPU, memory, storage, and artifact limits.

## Hard exclusions

No Windows unlock bypass, credential harvesting, stealth persistence, covert capture, keylogging, security-tool disabling, or autonomous permission expansion.

## Security lifecycle

Threat model each new capability, add abuse tests, review adapter code, run static/dependency/secret scanning, sign artifacts, stage rollout, and maintain revocation. Security incidents follow contain → preserve evidence → revoke → remediate → notify → learn.
