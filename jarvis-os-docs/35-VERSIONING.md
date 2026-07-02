# Versioning

## Version domains

- Product releases: SemVer `MAJOR.MINOR.PATCH`, with prereleases.
- REST: major in path (`/v1`); compatible fields evolve within major.
- Events/actions/prompts/plugins: independent SemVer stored in every artifact.
- Database/checkpoints: monotonic migration/schema versions.
- Models/evals/policies: immutable IDs plus human-readable revision.

## Compatibility

Adding optional fields is normally compatible. Removing/renaming fields, tightening accepted values, changing meaning/defaults, or making optional data required is breaking. Readers ignore unknown optional fields; writers do not send fields beyond negotiated capability. Desktop and backend negotiate supported contract ranges at connection.

## Release record

Each release lists product version, commit, contract/event/policy/prompt versions, DB migration range, model/provider matrix, minimum Windows/.NET/Python versions, SBOM/signatures, upgrade and rollback instructions, known issues, and evaluation report.

## Deprecation

Announce with replacement and removal version, instrument usage without personal content, support at least one normal release window, then remove only in a major contract release. Security revocation may be immediate.

Do not encode dependency versions in architecture prose as a substitute for lockfiles.
