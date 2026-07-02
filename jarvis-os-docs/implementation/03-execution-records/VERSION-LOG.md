# Step-by-Step Version Log

Product, contracts, prompts, policy, migrations and agents version independently. Append one record for every release candidate and shipped change.

## Entry template

### VERSION-X.Y.Z[-prerelease] — Date

| Domain | Old | New | Compatibility/migration |
|---|---:|---:|---|
| Product | | | |
| REST | | | |
| Action contracts | | | |
| Events | | | |
| Policy | | | |
| Prompts/agents | | | |
| Database | | | |
| Desktop/backend minimum | | | |

- Global IDs changed:
- Added/deprecated/removed:
- Security/privacy changes:
- Upgrade steps:
- Rollback steps:
- Evaluation/test report:
- SBOM/provenance/signatures:
- Known issues:

## VERSION-0.0.0-design — 2026-07-02

| Domain | Old | New | Compatibility/migration |
|---|---:|---:|---|
| Product | none | design baseline | no executable product |
| REST | none | proposed v1 | documentation only |
| Action contracts | none | proposed v1 | Stage 00 must create fixtures |
| Events | none | proposed v1 | Stage 00 must create fixtures |
| Policy | none | proposed v1 | not executable |
| Prompts/agents | none | proposed v1 | not deployed |
| Database | existing `jarvis` schema | unchanged | no tables/migrations |
| Desktop/backend minimum | none | proposed supported toolchains | pin during Stage 00 |

- Global IDs changed: initial allocation 110000–200010.
- Known issues: application repository, contracts, migrations, backend and desktop are not implemented.
