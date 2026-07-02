# Plugin System

Plugins extend typed capabilities, not raw model authority.

## Package

A signed package contains manifest, publisher identity, version, minimum host/API versions, declared capabilities/resources/network destinations, schemas, entry point, integrity hashes, privacy statement, and uninstall behavior.

## Runtime

Run out of process under a restricted token/job/container where practical. Plugins receive short-lived capability tokens and opaque secret handles. Network and filesystem access are denied unless declared and granted. Calls have deadlines, quotas, structured logs, and circuit breakers.

## Lifecycle

Discover → verify signature/reputation → display permissions → install with approval → disabled-by-default activation → health check → update with permission diff → disable/revoke → uninstall and remove owned data.

First-party plugins obey the same model. Native in-process plugins are postponed until a compelling performance requirement survives security review.
