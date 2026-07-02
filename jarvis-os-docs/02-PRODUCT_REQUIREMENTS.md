# Product Requirements

## MVP scope

### PR-1 Project registry

Users can register, rename, disable, and select local projects. A project stores an immutable ID, canonical path, approved commands, expected services, preferred apps, and health checks.

### PR-2 Task conversation

Text input creates a task. The UI streams status, plan, approval cards, action results, and a final verified summary. Users can cancel at any time.

### PR-3 Continue-project workflow

The system inspects Git status, validates required tools, proposes pull/start/open actions, honors local changes, starts approved services, opens configured applications, runs health checks, and reports failures.

### PR-4 Permission center

Users can inspect capability grants, revoke them, choose ask/allow/deny within permitted bounds, and review an audit trail. High-risk policy cannot be weakened by a prompt.

### PR-5 Durable tasks

Tasks survive backend or desktop restart. Awaiting approvals remain awaiting approval; side effects do not repeat merely because execution resumes.

### PR-6 Model providers

At least one local provider is supported. Cloud providers are opt-in and the UI previews what data class may leave the device.

### PR-7 Accessibility and privacy

The desktop shell supports keyboard navigation, screen readers, reduced motion, visible recording indicators, retention controls, data export, and deletion.

## Quality attributes

- Security: deny by default; no model-to-OS trust.
- Availability: desktop commands remain usable if cloud providers fail.
- Performance: UI event p95 < 250 ms locally; idle CPU target < 1%.
- Reliability: action delivery is at-least-once, execution is effectively-once through deduplication.
- Auditability: every decision links task, plan, action, approval, execution, and verification IDs.
- Maintainability: modular monolith first; separately deploy only measured bottlenecks.

## Acceptance scenario

Given a registered clean project, when the user says “continue this project,” the plan is displayed, safe reads run, required approvals are collected, configured apps/services start, health checks pass, and the final UI names each verified component. With dirty Git state, JARVIS MUST NOT pull automatically and MUST present safe choices.
