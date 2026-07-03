# Architect Feature Coverage

## Purpose

This document compares the supplied “local-first Copilot + Alexa + Siri + Cursor +
AutoGPT + Windows” proposal with the existing JARVIS OS/Sriee architecture. It
prevents duplicate subsystems and records only genuine gaps. A mapped feature is
still `planned` unless its function row, code and testing record say `complete`.

## Comparison

| Proposed area | Existing ownership | Gap disposition |
|---|---|---|
| Layered memory, consolidation, forgetting, scoring, compression, vector search and encryption | `09-MEMORY_SYSTEM.md`, `10-RAG_ARCHITECTURE.md`, `140006–140012` | Already covered; implementation remains staged. |
| Agent registry and per-agent roles/tools/permissions | `08-AGENT_BLUEPRINT.md`, specialist prompts and component function maps | Already covered; bounded typed specialist coordination added as `120016`. |
| Tool registry | Capability manifests, `05A-FUNCTION_MAP.md`, implementation maps, plugin manifests | Already covered; maps remain the source of callable truth. |
| Prompt library | `prompts/`, master prompt and per-agent prompt contracts | Already covered; new prompts ship with their owning implemented function. |
| LangGraph state and decision engine | `06-LANGGRAPH_ARCHITECTURE.md`, `07-STATE_DESIGN.md`, `120000–120014` | Already covered: observe/plan/policy/approval/dispatch/verify. |
| Scheduler and workflow library | Companion routines, care reminders and task pipeline | General schedules, occasion reminders, periodic reports and safe templates added as `210017–210020`; see `46-SCHEDULER-WORKFLOWS.md`. |
| Personality modes | Sriee relationship profile, coach profile and lifestyle mode `220022` | Already covered; media/routine preferences added under `230000`, `230013`. |
| Context engine | `120002`, UIA/OCR/vision, memory, connectors and briefings | Already covered; every source remains permissioned and freshness-tagged. |
| Knowledge engine | RAG `140010–140011`, browser/plugins, local documents | Already covered; external sources remain untrusted and cited. |
| Opt-in learning of habits/preferences | Memory consent flow, `210006–210007`, coach learning functions | Already covered; lifestyle interests are explicit under `230012–230015`. |
| Conversation tone and user-reported mood | Sriee dialogue/boundaries and `220021` | Already covered without hidden emotion inference. |
| Vision, OCR, QR, document and screen understanding | `180006–180016` | Covered; general face recognition remains intentionally excluded in favor of enrolled local matching. |
| Voice, wake word, STT/TTS, interruption and noise | `180000–180005` | Optional low-assurance enrolled-speaker verification added as `180017`; never sole high-risk authentication. |
| Desktop, browser and developer automation | `150xxx`, `160xxx`, `170xxx`, browser/plugin contracts | Already covered; every mutation follows normal policy/approval/receipt rules. |
| Health assistant | `220016–220024` | Already covered as general wellness only, never diagnosis or treatment. |
| Plugin SDK, events, manifests, signing and marketplace | `21-PLUGIN_SYSTEM.md`, `200000–200010` | Already covered; marketplace remains staged behind trust and sandbox gates. |
| Self-improvement/reflection | Verification and immutable evidence existed | Reviewable reflection candidates added as `120015`; automatic self-modification is prohibited. |
| Multi-agent collaboration | Agent blueprint and bounded specialists existed | Explicit typed coordinator added as `120016`; depth two and no model side effects. |
| Security permission levels and audit | `19-SECURITY_MODEL.md`, `20-PERMISSION_SYSTEM.md`, `130xxx` | Already covered with R0–R4 rather than vague low/medium/high labels. |
| Observability | `39-MONITORING.md`, `190000–190011` | Already covers time, component, duration, model usage, result/error and recovery without raw prompt/secret logging. |
| Music, favourites, playlists and local library | High-level roadmap only | Full first-party allocation added as `230000–230017`; see `45-LIFESTYLE-ENTERTAINMENT.md`. |
| Hobbies, routines, preferences, celebrations and recommendations | Partial companion/coach coverage | Explicit reviewable lifestyle allocations added as `230012–230015`. |
| Mobile, wearables, smart home, satellites, multi-device/family/enterprise, karaoke and multi-room | Future ecosystem roadmap | Remain future until separate privacy, trust, synchronization and provider threat models exist. |

## Architectural decisions

1. Existing documents are extended rather than copied into a second numbering tree.
2. “Emotion context” means user-reported mood or a selected mode, never inferred fact.
3. Face/voice matching may personalize; trusted OS/session authentication remains
   mandatory for consequential actions.
4. Reflection creates a candidate for human review. Sriee cannot silently rewrite
   her prompts, policies, tools, tests or memories.
5. Music providers use plugins/opaque credential references. Local libraries use
   registered roots and never expose raw paths or audio to a model by default.
6. A routine or workflow template is not authority: each resulting action is
   revalidated, policy-evaluated, approved when required, executed and verified.

## Status

This comparison adds planned specifications only. It does not claim runtime music,
scheduling, voice authentication, reflection or multi-agent orchestration exists.
