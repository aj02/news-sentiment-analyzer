# Prompt changelog

Versioned prompts live in numbered subdirectories. The active version is selected via `PROMPT_VERSION` in `.env`.

## v2 (current)

- Added 3 few-shot examples (neutral / negative / ambiguous) demonstrating the expected JSON shape.
- Added Hard Rule 2: confidence < 0.5 forces label to `neutral` and score into [-0.2, 0.2].
- Added Hard Rule 1: every claim/entity must be traceable to the article text — no outside knowledge.
- Added Hard Rule 4: explicit fallback for non-substantive content (paywall stubs, error pages).
- Tightened `entities[].sentiment` definition: "how the article portrays the entity," not the entity's own stance.
- Tightened `stance` taxonomy: `asserted` / `reported` / `speculated`, with examples.

## v1

- Initial version: role + JSON schema only, no few-shot, no guardrails. Kept committed for reference.
