# Versioning Log — 110000 Load Settings v1

| Field | Value |
|---|---|
| Record | VERSION-110000-v1 |
| Date | 2026-07-02 |
| Function version | v1 |
| Lifecycle | current |
| Compatibility | first implementation |

## Added

- Immutable `Settings` contract.
- `load_settings` and canonical `loadSettings` entry points.
- `SettingsLoadError` sanitized failure contract.
- Environment, PostgreSQL, Redis, JWT and logging fields.
- `jarvis` schema enforcement.
- Staging/production safety validation.
- Redacted diagnostics and safe fingerprint.

## Package changes

All additions are exact pins in root `requirements.txt`:

- `annotated-doc==0.0.4`
- `fastapi==0.138.1`
- `iniconfig==2.3.0`
- `pluggy==1.6.0`
- `pydantic-settings==2.14.2`
- `pytest==9.1.1`
- `starlette==1.3.1`

Existing pins used directly by this function remain:

- `pydantic==2.13.4`
- `pydantic_core==2.46.4`
- `python-dotenv==1.2.2`

## Configuration compatibility

- `NODE_ENV=developement` is intentionally rejected; use `NODE_ENV=development` or `JARVIS_ENV=development`.
- Use `JARVIS_DEBUG`, not generic `DEBUG`.
- `DEFAULT_SCHEMA` must be `jarvis`.
- Access and refresh JWT secrets must be distinct and at least 32 characters.

No database migration or API contract version change is included.
