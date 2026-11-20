# FinShield web (Next.js)

Static-export Next.js 14 app (App Router, TypeScript). Ported from the legacy `finshield2/frontend` dashboard and wired to the Lambda API in `../contract/openapi.yaml` through `lib/api.ts`.

```
npm install
npm run dev:mock     # contract fixtures, no API, no sign-in; "View as" role switcher in the sidebar
npm run dev          # live API: needs .env.local (run `make env` from the repo root, or copy .env.example)
npm run build        # static export to out/
```

Pages: Overview, Incidents (`/incidents/?id=ALR-…`), Approvals, Regulator deadlines, Compliance, Detection accuracy (Admin), Simulator (Admin), Audit evidence.
Sign-in is Cognito USER_PASSWORD_AUTH; menu items and buttons follow the Cognito groups (`can` in `lib/api.ts`).
