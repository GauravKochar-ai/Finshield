---
inclusion: always
---
<!------------------------------------------------------------------------------------
   Add rules to this file or a short description and have Kiro refine them for you.
   
   Learn about inclusion modes: https://kiro.dev/docs/steering/#inclusion-modes
-------------------------------------------------------------------------------------> 

# Tech rules
- AWS SAM, one template: infra/template.yaml. Region ap-south-1. Names finshield-${Stage}-<name>.
- Lambdas: Python 3.12, arm64, boto3, handler app.handler, shared code only from the finshield layer.
- No hardcoded ARNs, table names or model IDs: env vars from the template, runtime settings from SSM /finshield/dev/.
- Every function: structured JSON logging, idempotent on event_id, pytest with a fixture from contract/fixtures.
- Code computes every number, score and severity. Bedrock only writes words, validated against contract schemas.
- Bedrock via Converse API, temperature 0, Guardrail applied, input masked (no names, no Aadhaar, no PAN).
- Containment must be reversible and honour containment_mode LIVE or DRY_RUN.
- Frontend: existing Next.js app in web/, TypeScript, static export, reads only the REST API in contract/openapi.yaml.
- Least-privilege IAM per function. No role may Update/Delete on the Evidence table.