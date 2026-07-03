# Scheduler and Workflow Library

## Scheduler contract

Personal schedules support one-time and recurring triggers with IANA timezone,
local display time, next occurrence, acknowledgement, snooze, pause, expiry, quiet
hours and deletion. Recurrence must define DST gaps/overlaps, missed runs, clock
changes, restart recovery and duplicate delivery. The scheduler records intent and
wakes a task; it never executes an OS/provider action directly.

Morning/evening routines, daily planning, study/health reminders, night summaries,
weekly/monthly reports, birthdays, anniversaries and festivals are independently
enabled. Sensitive wellness reminders keep their separate data classification.

## Workflow templates

Initial templates may include:

- Open Project
- Start Coding / Focus Session
- Docker Development Session
- Meeting Preparation
- Interview Practice
- Debugging
- Deploy Preview
- Morning Routine
- Good Night
- Vacation Mode

A template is versioned declarative data with typed parameters, declared
capabilities, dependency graph, expected verification and rollback notes. It cannot
contain arbitrary shell text or become trusted because it shipped with Sriee.

At run time, every template instance enters the standard task flow:

`normalize → context → plan → validate → policy → approval → dispatch → verify`

Current grants, resources, policy and approval are rechecked. Partial failure is
reported honestly; automatic retries are bounded and never repeat an uncertain side
effect.

## Periodic reports and occasions

Weekly/monthly reports use only selected aggregate sources and cite freshness.
They avoid productivity, health and mood scores. Occasion records are explicit,
encrypted where personal, independently deletable and never inferred from contacts
or messages. Sending greetings, buying gifts or posting publicly is always a
separate previewed action.

## Security and testing

Required tests cover timezone/DST tables, crash recovery, duplicate fire,
cancellation races, quiet hours, revoked grants, modified templates, action
idempotency, missed occurrence policy, private notification rendering and deletion.

Functions `210017–210020` own the companion-facing schedule/report/template
behavior. Existing task, policy, executor, event, notification and audit components
remain authoritative.
