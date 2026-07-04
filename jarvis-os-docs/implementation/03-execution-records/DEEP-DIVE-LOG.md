# Step-by-Step Deep-Dive Log

Create a deep dive for a consequential decision, incident, security finding, unexpected production behavior or evidence that invalidates an assumption.

## Entry template

### DD-YYYYMMDD-NNN — Question

- Global IDs/stage:
- Context/deadline:
- Evidence and measurements:
- Constraints:
- Options considered:
- Experiments:
- Decision:
- Tradeoffs:
- Security/privacy effect:
- Confidence/unknowns:
- Revisit trigger/date:
- ADR/issues/tests:

## DD-20260702-001 — Separate planning from execution

- Global IDs/stage: 120004–120011, 130003–130006, 160001–160013 / foundation.
- Evidence: model behavior is probabilistic; Windows actions require local identity, canonical resources, receipts and native verification.
- Options: direct Python tools; C# executes model prose; C# executes typed policy-validated actions.
- Decision: typed actions with independent local policy and action-bound approval.
- Tradeoff: more contract work in exchange for an enforceable security and recovery boundary.
- Revisit: transport can evolve; authority separation does not.

## DD-20260702-002 — Isolate database objects in `jarvis`

- Global IDs/stage: 140000–140005 / infrastructure.
- Evidence: user supplied an existing database used by another application and requested a separate project schema.
- Decision: all JARVIS objects MUST be schema-qualified under `jarvis`; migrations MUST prove they do not modify `public` or unrelated schemas.
- Security/privacy effect: credentials are never copied into source or documentation and should be rotated after plaintext exposure.
- Revisit: separate database/role before production isolation or scaling.

## DD-20260705-001 — Protect per-install device keys

- Global IDs/stage: 130000 / desktop transport.
- Context/deadline: Device registration must bind an installation to the interactive
  Windows user without making private identity material available to Python, storage,
  logs or the backend.
- Evidence and measurements: Windows CNG supports current-user persisted P-256 keys,
  disabled export policy and public-key export through the platform provider.
- Constraints: setup must be explicit; service/session identities cannot register;
  database state contains only public identity; failed persistence must not leave a
  newly generated orphan key.
- Options considered: random shared secret in a file; DPAPI-wrapped software key;
  current-user CNG persisted key.
- Experiments: focused tests exercise consent, trusted identity, non-rebinding,
  concurrency, registry rollback and real CNG persistence/public export.
- Decision: use a P-256 key in the Microsoft Software Key Storage Provider, current
  user scope, with export policy zero. Derive the device ID from SHA-256 of the SEC1
  public key and persist only the public registration record.
- Tradeoffs: Windows CNG couples production key storage to Windows; protocols and
  in-memory fakes keep deterministic unit testing possible.
- Security/privacy effect: caller-supplied actor identity is impossible, private key
  bytes never cross the CNG boundary, repeat setup cannot rebind an install, and
  public registry failures trigger best-effort deletion of newly created keys.
- Confidence/unknowns: high for Microsoft Software KSP. Hardware-backed availability
  and attestation are not claimed and can be introduced behind the key-store protocol.
- Revisit trigger/date: before 130001 signing/proof implementation or adding another
  operating system.
- ADR/issues/tests: Global ID 130000 coding/version/testing records and
  `test_device_identity.py`.

## DD-20260705-002 — Bind and rotate loopback sessions

- Global IDs/stage: 130001, compatible with 110002 / desktop transport.
- Context/deadline: A loopback peer must not gain desktop authority merely by
  reaching the API, replaying a proof or retaining an older session token.
- Evidence and measurements: the registered CNG P-256 key can sign a canonical
  transcript without private export; the backend can validate SEC1 public material.
- Constraints: challenges and sessions are short lived; actor identity comes from
  registration; request authentication already consumes per-request nonces; contract
  negotiation must remain compatible with 110002.
- Options considered: loopback address trust; shared desktop secret; reusable signed
  assertion; one-time asymmetric challenge with epoch rotation.
- Experiments: live CNG signing/backend verification, eight-way replay race, invalid
  proof recovery, old-session revocation and end-to-end request authentication.
- Decision: issue 30-second, device-bound random challenges. Sign a domain-separated
  canonical transcript covering server/client nonces, backend instance, registered
  actor/device, Windows session and contract range. Consume only a valid proof, then
  atomically revoke the prior session, increment epoch and issue a five-minute token.
- Tradeoffs: the backend adds a pinned cryptographic verifier and durable deployments
  must implement the challenge/rotation protocols atomically. The in-memory parity
  stores are bounded but are not multi-process production persistence.
- Security/privacy effect: loopback reachability confers no identity; proof replay,
  signature substitution, cross-backend use, actor/device/key mismatch and stale
  sessions fail closed. Tokens and proof material are never logged.
- Confidence/unknowns: high for desktop-to-backend authentication and binding. A
  future packaged desktop must pin or otherwise authenticate the backend process if
  protection from a malicious local reverse proxy is required.
- Revisit trigger/date: before exposing handshake routes or implementing 150001.
- ADR/issues/tests: Global ID 130001 records and `test_session_auth.py`.

## DD-20260705-003 — Keep the local policy baseline authoritative

- Global IDs/stage: 130002 / desktop transport.
- Context/deadline: the model and backend are untrusted policy inputs; neither may
  replace the desktop's minimum restrictions or turn a denial into authority.
- Evidence and measurements: .NET 10 provides platform ECDSA P-256 verification,
  immutable collections and strict JSON unmapped-member handling without a runtime
  package. The 26-test suite exercises forgery, ambiguity and overlay abuse.
- Constraints: baseline is packaged locally, signer identity is pinned, default is
  always deny, unknown versions fail, local admin/user customization remains useful,
  and no raw policy content enters diagnostics or the effective object.
- Options considered: unsigned JSON; signed baseline with arbitrary overlay
  replacement; signed baseline with ordered tightening-only overlays.
- Experiments: payload/key/signature tampering, duplicate properties, unknown fields,
  noncanonical versions, rule limits, overlay relaxation, source mutation between
  reads and deterministic Release builds with warnings as errors.
- Decision: sign a domain-separated v1 envelope over exact payload bytes with
  P-256/SHA-256 and a pinned key ID. Require a strict `1.x.y` deny-default document.
  Apply admin then user overlays only when every rule is known and no decision moves
  upward through `deny < ask < allow`.
- Tradeoffs: v1 intentionally excludes wildcard/resource predicates until evaluation
  contract 130003 defines them. Any malformed local overlay blocks policy load rather
  than being silently ignored.
- Security/privacy effect: backend/model data is absent from the loader API; unknown
  capabilities deny; overlays cannot expand authority; source buffers are copied
  immediately to close mutation races; returned state is immutable and public-only.
- Confidence/unknowns: high for load-time authenticity and monotonic overlay merge.
  Package installer ACL/signing integration remains a later desktop composition task.
- Revisit trigger/date: before implementing 130003 or adding policy schema v2.
- ADR/issues/tests: Global ID 130002 records and
  `PolicyBaselineLoaderTests.cs`.
