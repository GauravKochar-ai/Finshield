# Requirements: M8 Compliance, pitch and demo

Owner: M8. Needs from: Everyone's screenshots. Gives to: Deck and regulation texts for M5.

Steering: `.kiro/steering/*`. Contract: `contract/` (config.json, schemas, openapi.yaml, fixtures). Playbook: `docs/playbook.md`. Contract changes go to `contract/CHANGES.md`, never silently.

## User story

As the compliance and pitch owner, I want verified regulation summaries, a compliance map and a rehearsed demo, so every clause we cite is accurate and the story lands in six minutes.

## Requirements

### R1. Compliance map

1.1. THE SYSTEM SHALL provide `docs/compliance-map.md` with one row per obligation: FinShield control, evidence produced and the screen that shows it.
1.2. THE SYSTEM SHALL use only "DPDP-aligned readiness and controls", call the consent component a "consent ledger", and mark every clause number that still needs checking against the official text.

### R2. Regulation summaries

2.1. THE SYSTEM SHALL provide one markdown summary per regulation (DPDP Act 2023 and Rules phasing, RBI Digital Lending Directions, RBI IT governance and cyber security directions for NBFCs, RBI IT outsourcing directions, CERT-In 2022 directions), each with clause id, plain summary and why it matters to a digital lender, uploaded to `finshield-dev-rules`.
2.2. THE SYSTEM SHALL check each clause against the official text before it is used in config, prompts, the web app or the deck.

### R3. Demo and deck

3.1. THE SYSTEM SHALL provide a 6-minute `docs/demo-script.md` with exact clicks, what to say and fallbacks, and an 8-slide deck.
3.2. THE SYSTEM SHALL show deadlines as RBI 6 h, CERT-In 6 h and Data Protection Board detailed report 72 h from `detected_at`, as configured readiness timers.

### R4. Business case

4.1. THE SYSTEM SHALL describe buyers, price tiers and AWS cost per million events, and ship an architecture diagram.

## Done when

The deck, demo script and backup video are final at CP5 and every cited clause is verified.
