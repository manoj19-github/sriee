# Docker Agent

The Docker agent operates on registered projects and named Compose resources.

## Capabilities

Inspect daemon/version, validate Compose config, build declared services, start/stop project services, inspect health, and read bounded logs. Image pulls, network creation, volume mutation, and cleanup have distinct risk.

## Policy

Never mount arbitrary host roots, expose the Docker socket to workloads, run privileged containers, inject unapproved secrets, or use floating images in production recipes. `prune`, volume deletion, and removal of non-project resources are high-risk and denied by default.

## Verification

Starting a container is insufficient. Check Compose state, health checks, expected ports on intended interfaces, and bounded application probes. Results list image digests and resource names. Rollback stops only resources created by the task unless the user approves broader scope.
