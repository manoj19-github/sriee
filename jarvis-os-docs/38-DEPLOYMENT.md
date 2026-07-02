# Deployment

## Local production topology

Install a signed per-user WPF application and a supervised local backend. Bind to loopback, create per-install credentials, initialize encrypted user data, run readiness checks, and show explicit cloud-provider setup only when requested.

Do not require Docker Desktop for the core product; it is a developer integration, not a runtime dependency. PostgreSQL may begin as a managed local service for development; packaging must define backup, upgrades, ports, credentials, and uninstall behavior. An embedded alternative can be evaluated for consumer distribution.

## Upgrade

Download signed manifest → verify channel/version/hash/signature → display material permission/privacy changes → quiesce tasks safely → backup/migrate → install atomically → health check → resume compatible tasks. Keep a rollback package and database compatibility window.

## Uninstall

Stop processes, revoke device credentials, remove binaries/services, and offer separate choices to retain/export or securely delete user data. Never silently delete project files or plugin-owned external data.
