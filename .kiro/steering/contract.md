---
inclusion: always
---
<!------------------------------------------------------------------------------------
   Add rules to this file or a short description and have Kiro refine them for you.
   
   Learn about inclusion modes: https://kiro.dev/docs/steering/#inclusion-modes
-------------------------------------------------------------------------------------> 

# Contract (source of truth: contract/)
Unified event, alert, AI explanation, evidence entry and REST API are defined in contract/schemas and contract/openapi.yaml.
Scoring points, thresholds and deadlines live ONLY in contract/config.json.
EventBridge bus finshield-dev-bus; detail-types: Raw Activity, Normalized Event, Alert Raised, Incident Updated.
One open alert per user per 60-min window; Step Functions execution name = <alert_id>-<severity>.
If a change to the contract seems needed, stop and write it to contract/CHANGES.md for the integration lead.