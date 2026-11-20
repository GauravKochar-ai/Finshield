# FinLend Ops (user-web)

Staff portal of FinLend, the sample digital lender that FinShield monitors. Collections, marketing and ops staff
(Cognito group `Staff`) look up their customers, open and upload KYC documents and read the consent ledger. Every
call goes to the `/staff/*` routes in `contract/openapi.yaml`; the staff API emits each view, download and upload as
an activity event, so FinShield sees what staff do here. When FinShield contains a user, the API answers
`403 ACCESS_CONTAINED` and this app shows the containment banner.

All customer data is synthetic and marked SAMPLE.

## Run

```bash
npm install
cp .env.example .env.local   # or `make env` from the repo root, which writes it from the deployed stack
npm run dev                  # http://localhost:3003, signs in with Cognito
npm run dev:mock             # http://localhost:3003, no sign-in, reads contract/fixtures/api_staff_*.json
```

## Build

```bash
npm run build                # static export to out/
npx tsc --noEmit
```

Pages: `/` (purpose of access, search by customer ID, my customers) and `/customer/?id=C-10001` (customer card,
KYC documents with View, Download and Upload, read-only consent ledger).
