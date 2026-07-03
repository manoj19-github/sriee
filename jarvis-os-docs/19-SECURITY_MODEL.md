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

## Preliminary plan-policy boundary

The backend graph performs a deterministic preliminary policy pass before approval or
dispatch. Its policy snapshot is reference-bound to the authenticated actor/device,
deny-by-default and schema validated. It stores only action ID, stable decision ID,
risk tier, fixed reason codes, policy reference/version, optional opaque grant
reference and fresh-approval requirement. It never stores policy internals or action
arguments in the decision record.

Combination rules evaluate the plan as a whole so repeated or related actions cannot
evade a stricter rule by risk splitting. Unknown actions deny. R4 always denies; R3
cannot allow; R2 allow requires a snapshot-provided scoped grant reference.

Security-model output is untrusted advice. It may raise risk or tighten
`allow → ask → deny`; weaker/equal recommendations are ignored and malformed,
unavailable or unknown-action analysis fails closed. The graph cannot create a grant
or approval.

This boundary does not replace local enforcement. Immediately before execution, the
trusted desktop policy engine must re-resolve canonical resources, use current signed
policy/grants and validate the exact approval digest. A graph `allow` is never an
executor authorization by itself.

## Security lifecycle

Threat model each new capability, add abuse tests, review adapter code, run static/dependency/secret scanning, sign artifacts, stage rollout, and maintain revocation. Security incidents follow contain → preserve evidence → revoke → remediate → notify → learn.
