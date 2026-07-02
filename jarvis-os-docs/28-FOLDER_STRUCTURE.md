# Folder Structure

```text
jarvis-os/
├─ backend/
│  ├─ src/jarvis/{api,application,domain,graph,policy,providers,persistence}
│  ├─ tests/{unit,contract,integration,evaluation}
│  └─ migrations/
├─ desktop/
│  ├─ src/{Jarvis.Desktop,Jarvis.Core,Jarvis.Contracts,Jarvis.Executor,
│  │        Jarvis.Windows,Jarvis.Security,Jarvis.Telemetry}
│  └─ tests/
├─ contracts/{openapi,events,actions,policy}
├─ plugins/{sdk,samples}
├─ evals/{datasets,scorers,reports}
├─ infra/{compose,otel,packaging}
├─ docs/{adr,runbooks,threat-models}
├─ scripts/
├─ global.json
├─ pyproject.toml
└─ README.md
```

Dependencies point inward: adapters → application → domain. Contracts have no runtime framework dependencies. Generated sources are clearly marked and regenerated in CI. Tests mirror production modules. Personal runtime data never lives inside the source tree.
