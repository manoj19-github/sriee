# Function Map — Developer Integrations

Source: [coding agent](../../14-CODING_AGENT.md), [Git agent](../../17-GIT_AGENT.md), and [Docker agent](../../16-DOCKER_AGENT.md).

Technology: registered CLI adapters, Git, Docker/Compose, VS Code, project runbooks.

| Global ID | Canonical name | Function | Description | Reads | Writes | Status | Notes |
|---|---|---|---|---|---|---|---|
| 170000 | `shared-project-register-project-mandatory-p0-planned-current-v1` | `registerProject` | Creates project record from canonical root, display name, tools, runbook and health checks. | user input; filesystem/tool observations | db: project configuration | planned/current/v1 | Duplicate/symlink-equivalent roots detected. |
| 170001 | `csharp-project-inspect-workspace-mandatory-p0-planned-current-v1` | `inspectProjectWorkspace` | Reads bounded project metadata, instruction files, dirty state and declared dependencies. | filesystem; Git; project config | api/graph: project observation | planned/current/v1 | Read limits and sensitive-file exclusions apply. |
| 170002 | `shared-project-build-continue-plan-mandatory-p0-planned-current-v1` | `buildContinueProjectPlan` | Converts runbook/current state into minimal open/start/check plan with dependency ordering. | project observation; runbook; capabilities | graph: typed plan actions | planned/current/v1 | Dirty Git prevents automatic pull. |
| 170003 | `csharp-vscode-open-workspace-mandatory-p0-planned-current-v1` | `openVsCodeWorkspace` | Opens registered VS Code executable at canonical project root and verifies matching window/process. | app/project registry | OS: VS Code process/window | planned/current/v1 | Workspace trust remains visible/user-controlled. |
| 170004 | `csharp-git-inspect-repository-mandatory-p0-planned-current-v1` | `inspectGitRepository` | Returns root, branch, clean/dirty, ahead/behind, conflict and redacted remotes. | Git repository | graph: Git observation | planned/current/v1 | Never reads credential material. |
| 170005 | `csharp-git-fetch-repository-mandatory-p1-planned-current-v1` | `fetchGitRepository` | Fetches configured remote with timeout/credential handle and verifies refs. | project/remote config; credential handle | Git refs; receipt | planned/current/v1 | Network action; no worktree mutation. |
| 170006 | `csharp-git-update-working-copy-mandatory-p1-planned-current-v1` | `updateGitWorkingCopy` | Performs approved fast-forward/rebase strategy only after clean-state/conflict preconditions. | Git observation; exact approved strategy | Git worktree/refs; receipt | planned/current/v1 | Never silently stash/discard changes. |
| 170007 | `csharp-git-create-commit-optional-p1-planned-current-v1` | `createGitCommit` | Shows exact staged diff, scans secrets and creates local commit after approval. | worktree/index; commit metadata | Git commit/index; receipt | planned/current/v1 | Unrelated changes excluded. |
| 170008 | `csharp-git-push-remote-optional-p2-planned-current-v1` | `pushGitRemote` | Pushes exact local ref/commit range to normalized remote after R3 approval and verifies remote ref. | repository; approval; credential handle | external Git remote; audit | planned/current/v1 | Force push denied by default. |
| 170009 | `csharp-docker-validate-compose-mandatory-p1-planned-current-v1` | `validateComposeProject` | Parses normalized Compose config, checks prohibited mounts/privilege/ports and records image refs. | project Compose files; Docker daemon | graph: validation observation | planned/current/v1 | Docker socket/privileged containers denied by baseline. |
| 170010 | `csharp-docker-start-services-mandatory-p1-planned-current-v1` | `startComposeServices` | Starts only declared project services and returns resource/image identifiers. | validated Compose/project config | Docker: containers/networks; receipt | planned/current/v1 | Volume/network mutations carry explicit policy. |
| 170011 | `csharp-docker-check-health-mandatory-p1-planned-current-v1` | `checkComposeHealth` | Inspects state, health, intended port binding and bounded application probes. | Docker resources; project health checks | graph: verification evidence | planned/current/v1 | Running is not equivalent to healthy. |
| 170012 | `csharp-developer-run-command-mandatory-p0-planned-current-v1` | `runProjectCommand` | Runs registered build/test/dev ProcessSpec with resource limits and structured result. | project command registry | OS process; logs/receipt | planned/current/v1 | No raw shell interpolation. |
| 170013 | `shared-developer-summarize-readiness-mandatory-p0-planned-current-v1` | `summarizeProjectReadiness` | Reports apps, services, repository, checks, failures and recommended next action from evidence. | action results; health observations | task final response | planned/current/v1 | Explicitly labels unverified components. |

## Change rule

Update this map before changing project runbooks, executable/command registry, Git mutation, Docker scope, health checks, or developer workflow behavior.
