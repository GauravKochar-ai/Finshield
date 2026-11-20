---
inclusion: always
---
<!------------------------------------------------------------------------------------
   Add rules to this file or a short description and have Kiro refine them for you.
   
   Learn about inclusion modes: https://kiro.dev/docs/steering/#inclusion-modes
-------------------------------------------------------------------------------------> 

```
finshield/
  .kiro/steering/        product.md tech.md structure.md contract.md compliance.md
  .kiro/specs/           one folder per module (M1 generates)
  contract/
    config.json          scoring points, thresholds, deadlines (single source of truth)
    openapi.yaml         REST API
    schemas/             event, alert, ai_explanation, evidence_entry, report (JSON Schema)
    fixtures/            one example per schema + one per API response
  infra/template.yaml    SAM, the only template; samconfig.toml (stage=dev)
  backend/
    shared/python/finshield/   schema.py ddb.py config.py evidence.py events.py bedrock.py (Lambda layer)
    functions/<name>/app.py    one folder per Lambda, handler = app.handler
    statemachines/incident.asl.json
    tests/                      pytest, one file per function
  simulator/seed/  simulator/scenarios/SC-01.json ... SC-10.json
  web/                   existing Next.js admin portal (static export)
  docs/                  compliance-map.md, demo-script.md, architecture.png
  scripts/               write-env.sh seed.sh scenario.sh smoke.sh
  Makefile
```

Put new Lambdas in backend/functions/<name>/ and register them in infra/template.yaml in the same change.
