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
