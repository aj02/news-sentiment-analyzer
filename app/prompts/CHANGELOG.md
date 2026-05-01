# Prompt changelog

Versioned prompts live in numbered subdirectories. The active version is selected via `PROMPT_VERSION` in `.env`.

## v3 (current)

- **Added three independent axes alongside polarity**:
  - `subjectivity` (factual ↔ opinionated) — distinguishes neutral wire reporting from op-eds at the same polarity.
  - `certainty` (hedged ↔ definitive) — captures whether claims are stated as fact or surrounded by `could` / `may` / `reportedly`.
  - `emotions` — Plutchik 8-emotion intensities (joy, trust, fear, surprise, sadness, disgust, anger, anticipation), each [0, 1], independent of polarity.
- **Added `aspects[]`**: aspect-based sentiment per topic within an article (e.g. "monsoon risk: negative" inside an otherwise-neutral RBI policy piece). Distinct from `entities` — aspects are issues, entities are people/orgs.
- **Added `quotes[]`**: direct quotes with `speaker`, `speaker_role`, quote-level sentiment, and `framing` (supportive / neutral / skeptical) — captures whether the surrounding article presents the quote as authoritative or undermines it.
- **Reworked few-shot examples** to Indian-context articles: RBI monetary policy, an Indian corporate-governance investigation, and a Bengaluru Suburban Rail groundbreaking — same three boundary cases (neutral / negative / low-confidence ambiguous) tuned for the audience.
- Hard Rule 2 (confidence < 0.5 → neutral) tightened: applies only to polarity, NOT to subjectivity/certainty/emotions.
- Hard Rule 6 added: "Independence of axes" — explicit reminder that subjectivity and certainty are NOT shortcuts for sentiment.

## v2

- Added 3 few-shot examples (neutral / negative / ambiguous) demonstrating the expected JSON shape.
- Added Hard Rule 2: confidence < 0.5 forces label to `neutral` and score into [-0.2, 0.2].
- Added Hard Rule 1: every claim/entity must be traceable to the article text — no outside knowledge.
- Added Hard Rule 4: explicit fallback for non-substantive content (paywall stubs, error pages).
- Tightened `entities[].sentiment` definition: "how the article portrays the entity," not the entity's own stance.
- Tightened `stance` taxonomy: `asserted` / `reported` / `speculated`, with examples.

## v1

- Initial version: role + JSON schema only, no few-shot, no guardrails. Kept committed for reference.
