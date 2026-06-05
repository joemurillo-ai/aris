# ARIS Relationship Ledger Schema

ARIS Relationship Ledger v0.1 is local-first and stores data as JSON in browser local storage. The model is intentionally close to a future SQLite schema.

## Contact

- `id`: stable local identifier
- `name`: person name
- `title`: role or relationship descriptor
- `organizationId`: linked organization
- `domain`: insurance, AI, mortgage, legal, or personal brand
- `email`, `phone`, `location`: contact details
- `relationshipScore`: trust and warmth from 1-10
- `strategicValueScore`: strategic value from 1-10
- `lastInteractionDate`: ISO date
- `nextFollowUpDate`: ISO date
- `tags`: context labels
- `context`: relationship notes

## Organization

- `id`, `name`, `domain`, `notes`

## Interaction

- `id`, `contactId`, `date`, `channel`, `summary`, `sentiment`

## Opportunity

- `id`, `contactId`, `title`, `value`, `stage`, `probability`, `nextStep`, `targetDate`

## Commitment

- `id`, `contactId`, `owner`, `promise`, `dueDate`, `status`

## FollowUpTask

- `id`, `contactId`, `title`, `dueDate`, `status`, `priority`

## Future AI Hooks

- `aris/scoring.ts`: deterministic scoring and future model-assisted score explanations
- `aris/briefing.ts`: relationship briefing generator placeholder
- `aris/prompts.ts`: prompt templates for future OpenAI integration
