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

## VERSION-0.1.0-design — 2026-07-02

| Domain | Old | New | Compatibility/migration |
|---|---:|---:|---|
| Product | task-focused JARVIS design | optional Sriee companion design | additive; companion mode defaults off |
| Policy | general sensor/privacy baseline | explicit sensor, biometric and companion boundaries | existing action tiers remain authoritative |
| Prompts/agents | no companion persona | proposed Sriee persona contract | documentation only; no runtime prompt deployed |
| Database | no companion/biometric tables | unchanged | storage design required before implementation |

- Global IDs changed: added planned `180011–180016` and `210000–210011`.
- Added: female voice profile, camera session, local presence, optional local face enrollment/matching, visible-expression cues, morning briefing, affectionate dialogue, routine suggestions, companion boundaries and standard capability routing.
- Security/privacy changes: no blanket machine-control permission; sensors remain visible and independently revocable; face match is personalization-only; expression cues cannot claim internal emotion.
- Upgrade steps: none; planning documentation only.
- Rollback steps: revert this design change; no runtime or stored data is affected.
- Evaluation/test report: documentation checks passed with 143 unique function rows, 18 new planned rows, matching dashboard totals, valid canonical statuses/columns and zero broken relative links.
- Known issues: all newly allocated functions remain planned.

## VERSION-0.2.0-design — 2026-07-02

| Domain | Old | New | Compatibility/migration |
|---|---:|---:|---|
| Product | Sriee companion baseline | consolidated 35-area roadmap plus romantic entertainment | additive; features remain disabled/unimplemented |
| Policy | general companion boundaries | explicit romance opt-in, intensity, rejection and serious-context rules | baseline safeguards cannot be disabled |
| Prompts/agents | affectionate dialogue proposal | proposed stories, jokes, playful flirting and evening briefing | documentation only; no runtime prompt deployed |
| Database | no relationship profile tables | unchanged | storage schema required before implementation |

- Global IDs changed: added planned `210012–210016`.
- Added: relationship style configuration, original romantic stories, jokes, bounded playful flirting and evening briefings.
- Security/privacy changes: romance is independently configurable; rejection is immediate; romantic language is suppressed in approval, emergency, financial/security and age-uncertain contexts.
- Upgrade steps: none; planning documentation only.
- Rollback steps: revert this design change; no runtime or stored data is affected.
- Evaluation/test report: passed with 148 unique function rows, 5 new planned companion rows, 35 roadmap areas, matching dashboard totals, valid map structure/status and zero broken relative links.
- Known issues: all five new functions and the consolidated roadmap remain planned.

## VERSION-0.3.0-design — 2026-07-02

| Domain | Old | New | Compatibility/migration |
|---|---:|---:|---|
| Product | companion/capability roadmap | developer coach and optional general-wellness design | additive; functions remain unimplemented |
| Policy | companion/privacy baseline | coaching truthfulness, proactive limits, wellness/medication/urgent-language boundaries | existing permissions remain authoritative |
| Prompts/agents | proposed companion prompts | proposed developer, learning, career and wellness coaching roles | documentation only; no runtime prompt deployed |
| Database | no coach/wellness schema | unchanged | separate sensitive storage design required |

- Global IDs changed: allocated planned `220000–220024`.
- Added: developer profile/briefings, workflow help, learning plans/sessions/quizzes/challenges, reviews/projects/achievements/career coaching, wellness connectors/records/reminders/check-ins and safety filter.
- Security/privacy changes: wellness data is separate sensitive data; cloud egress defaults off; no diagnosis, normality, treatment or medication-change advice.
- Upgrade steps: none; planning documentation only.
- Rollback steps: revert this design change.
- Evaluation/test report: passed with 173 unique function rows, 25 new planned rows, matching dashboard totals, valid structure/status and zero broken relative links.
- Known issues: all new functions remain planned; deployment-jurisdiction and connector-specific reviews are pending.
