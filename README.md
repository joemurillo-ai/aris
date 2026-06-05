# ARIS Relationship Ledger v0.1

ARIS Relationship Ledger is a local-first relationship intelligence dashboard for Joe Murillo. It tracks relationship context, trust, opportunity, momentum, commitments, and follow-up actions without using an external CRM or AI service.

## Stack

- Next.js
- TypeScript
- Tailwind CSS
- Browser local JSON storage through `localStorage`
- AI-ready placeholder architecture in `/aris`

## Features

- Executive command center dashboard
- Add, edit, and delete contacts
- Dedicated contact profile pages
- Interaction notes
- Follow-up tasks with due dates
- Opportunities linked to contacts
- Commitments and promises linked to contacts
- Relationship score from 1-10
- Strategic value score from 1-10
- Cold relationship indicator
- Seed data with 10 contacts across insurance, AI, mortgage, legal, and personal brand

## Run Locally

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Data Storage

The MVP stores ledger data locally in the browser under:

```text
aris-relationship-ledger:v0.1
```

Use the `Seed` button in the dashboard to reset the local data back to the sample dataset.

## ARIS AI-Ready Architecture

The `/aris` folder contains deterministic placeholders that can later call the OpenAI API:

- `scoring.ts`: relationship health, cold status, momentum, and opportunity priority helpers
- `briefing.ts`: relationship briefing placeholder functions
- `prompts.ts`: future prompt templates
- `schema.md`: entity model and future storage shape

No external AI calls are made in v0.1.

## Suggested Commit Messages

```text
feat: scaffold aris relationship ledger app
feat: add local-first relationship data model and seed records
feat: build executive dashboard and contact profile workflows
docs: add setup and architecture notes
```
