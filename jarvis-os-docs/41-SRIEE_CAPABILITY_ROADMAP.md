# Sriee and JARVIS Capability Roadmap

## Positioning

JARVIS OS is a local-first AI operating environment for developers and power users. Sriee is its optional female-voiced companion persona: affectionate when invited, practical during work, and governed by the same permissions as every other interface.

This roadmap consolidates the requested Siri/Alexa/Gemini/Copilot/ChatGPT-style capabilities without implying they already exist. Every item below is planned unless its function-map row and testing record say `complete`.

## Capability catalogue

| # | Area | Planned experience | Primary ownership |
|---:|---|---|---|
| 1 | Voice assistant | Wake word, natural multi-turn speech, interruption, VAD, noise handling, offline/online STT and female TTS. Voice matching may personalize but cannot authorize high-risk work alone. | Voice/vision `180xxx`; security `130xxx` |
| 2 | AI conversation | Contextual dialogue, approved long-term memory, humor, stories, translation, summarization, brainstorming, explanation and daily conversation. | LangGraph `120xxx`; memory `140xxx`; Sriee `210xxx` |
| 3 | Personal assistant | Morning/evening briefings with time, weather, calendar, reminders, tasks, GitHub, news, system health and goals. | Sriee `210002`, `210016`; connector plugins |
| 4 | Daily planner | To-dos, notes, goals, meetings, recurring tasks, focus timer, time blocking and Pomodoro. | Sriee/task APIs; calendar/task plugins |
| 5 | Smart reminders | One-time and recurring reminders with timezone, acknowledgement, snooze, expiry and quiet-hour behavior. | Task scheduler; desktop notifications |
| 6 | Coding assistant | Generate, explain, debug, review, refactor and test code; APIs, SQL, React, Flutter, FastAPI, Docker, Kubernetes, LangGraph and documentation. | LangGraph `120xxx`; developer `170xxx` |
| 7 | VS Code integration | Open projects, create/rename/search files, explain/fix errors, run/debug projects and install approved packages. | Developer `170000–170005`; executor `160xxx` |
| 8 | Git assistant | Clone, inspect, branch, commit, merge, explain conflicts, prepare pull requests, release notes and changelogs. | Developer `170006–170009` |
| 9 | Docker assistant | Build images, manage containers/Compose, view logs and verify health. | Developer `170010–170013` |
| 10 | Database assistant | PostgreSQL, MongoDB, MySQL and Redis query help, explain plans, backup/restore previews and performance analysis. | Data `140xxx`; scoped database plugins |
| 11 | Windows desktop control | Open apps and control windows, volume, brightness, Wi-Fi, Bluetooth, clipboard, notifications and monitor layouts where typed adapters exist. | Desktop `150xxx`; executor `160xxx` |
| 12 | File-system AI | Find, rename, copy, move and organize scoped files; duplicate/storage analysis. Destructive work requires preview and approval. | Executor `160002`, `160009`; policy `130xxx` |
| 13 | Browser agent | Open/search/read/summarize pages, fill forms and handle transfers under domain/resource permissions. Submission, upload and transactions require exact approval. | Browser specification; plugin/adapters `200xxx` |
| 14 | YouTube assistant | Search and control permitted playback for music/tutorials. It may use ordinary player controls but never bypass platform rules or protections. | Media/browser plugin |
| 15 | Music assistant | Spotify, YouTube Music and local-library playback, queue, pause/next and permitted volume control. | Media plugins; executor |
| 16 | Vision AI | Visible webcam sessions for presence, optional local face enrollment/matching, hand/pose observations, QR/document scanning and uncertain expression cues. | Voice/vision `180011–180016`; future typed observations |
| 17 | Screen understanding | Read permitted VS Code, browser, terminal, PDF, image, log, diagram and chart context with provenance. | Voice/vision `180006–180009` |
| 18 | OCR | Extract bounded text and geometry from permitted images, PDFs and screenshots. | Voice/vision `180007–180010` |
| 19 | Memory | Remember approved projects, coding style, commands, music and routines; inspect, correct, export, expire and delete records. | Data/memory `140006–140009`, `140012` |
| 20 | Learning | Propose patterns for IDE, hours, habits and tools; suggestions require confirmation before persistent memory or action. | Memory `140xxx`; Sriee `210006–210008` |
| 21 | AI coworker | Plan work, create scoped changes, run tests, explain outcomes and request approval for material actions. | LangGraph `120xxx`; executor/developer maps |
| 22 | Research agent | Research official documentation, repositories, APIs and papers; return concise source-linked summaries. | LangGraph specialist; browser/retrieval plugins |
| 23 | Email assistant | Read/summarize/categorize permitted mail and draft replies. Sending always uses recipient/content preview and approval. | Email plugin; policy `130xxx` |
| 24 | Calendar assistant | Read schedules, create events, prepare meeting links/reminders and weekly plans. Writes require scoped confirmation. | Calendar plugin; Sriee briefings |
| 25 | Notification center | Unify privacy-filtered GitHub, calendar, email, weather, task and system alerts with quiet hours. | Desktop `150010`; plugins |
| 26 | Home dashboard | User-configurable weather, calendar, CPU/RAM, Docker, GitHub, news, tasks, notes and music widgets. | Desktop `150xxx`; observability `190xxx` |
| 27 | Plugin marketplace | Signed third-party integrations such as Home Assistant, Slack, Discord, Jira, Trello and Notion. | Plugin platform `200xxx` |
| 28 | Multi-agent system | LangGraph coordinates bounded planner, coding, desktop, browser, vision, memory, research, Git, Docker, calendar, security, file and voice specialists. | LangGraph `120xxx`; agent blueprint |
| 29 | Automation | Scheduled routines such as opening an approved development workspace at 9 AM. Each action retains its normal scope and approval tier. | Scheduler; Sriee routines; executor |
| 30 | Smart suggestions | Capped, dismissible suggestions for failed builds, breaks and resource pressure rather than frequent interruptions. | Sriee `210008`; observability `190xxx` |
| 31 | Security | Local session authentication, permission center, audit trail, encryption and OS-backed authentication. Face matching personalizes only; Windows Hello may authenticate through OS APIs. | Security `130xxx`; desktop `150008–150009` |
| 32 | Offline AI | Optional local STT/TTS, embeddings and language models with explicit cloud routing and data-egress policy. | Infrastructure/provider layer |
| 33 | Developer mode | Scoped terminal, Docker/Kubernetes, Git, API/database testing and log analysis with stronger previews and receipts. | Developer `170xxx`; executor `160xxx` |
| 34 | System health | Monitor CPU, RAM, GPU, disk, network, battery and available temperatures with thresholds and privacy-safe history. | Observability `190xxx`; native adapters |
| 35 | Future ecosystem | Smart-home, mobile, wearable, multi-device, multi-user, custom-agent, plugin SDK and enterprise modes after separate threat models. | Plugin platform and future allocations |

## Sriee romantic companion mode

Sriee can tell original romantic stories, tell jokes, offer affectionate compliments and engage in gentle or playful non-explicit flirting when romantic mode is enabled. Relationship style, flirt intensity, preferred terms, excluded topics, private mode and quiet hours are independently configurable.

Romantic language stops immediately when asked and is suppressed during approvals, emergencies, distress, financial/security decisions and other serious contexts. Affection never changes permissions, pressures continued engagement, fabricates shared real-world memories, or claims Sriee is human.

## Delivery rule

Capabilities ship in narrow vertical slices. A roadmap entry becomes real only after function allocation, threat/privacy review, typed contracts, visible permissions, failure behavior, deterministic tests, user-facing controls, rollback and delivery logs are complete.
