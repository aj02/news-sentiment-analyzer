# Example outputs

Committed JSON outputs so visitors can see the exact shape the service produces
without having to run it. Every file here is the body of `POST /analyze` for a
real Indian news article URL, in the v3 schema (polarity + subjectivity +
certainty + emotions + aspects + quotes + entities + key_claims + topics).

Every file validates against `app.schemas.responses.AnalyzeResponse` — run
`python examples/validate.py` to confirm.

| File                                                | Source            | Domain                          | Polarity            |
|-----------------------------------------------------|-------------------|---------------------------------|---------------------|
| `01_thehindu_rbi_policy_neutral.json`               | The Hindu         | RBI monetary policy             | neutral             |
| `02_mint_corporate_governance_negative.json`        | Mint              | Corporate governance scandal    | negative            |
| `03_thehindu_isro_launch_positive.json`             | The Hindu         | ISRO PSLV launch                | positive            |
| `04_indianexpress_bengaluru_rail_clamped.json`      | The Indian Express| Bengaluru Suburban Rail         | neutral (clamped)   |

## What to look at in each example

- **`01_thehindu_rbi_policy_neutral.json`** — neutral wire reporting. Note the
  high `certainty` (0.88) and very low `subjectivity` (0.10). The interesting
  detail is in **`aspects`**: an otherwise-neutral piece is broken down into
  `monsoon risk: negative`, `GDP growth: positive`, and `repo rate trajectory:
  neutral` — which is exactly the kind of structure aspect-based sentiment was
  designed to surface.
- **`02_mint_corporate_governance_negative.json`** — investigative piece.
  `subjectivity` rises to 0.45 (more editorialized framing); `disgust` and
  `anger` dominate the `emotions` block; the only quote is framed as
  *supportive* — the article presents the resigned director's voice as
  authoritative.
- **`03_thehindu_isro_launch_positive.json`** — clearly positive coverage.
  `certainty` is very high (0.92) because the events are concrete and confirmed.
  Multiple aspects all skew positive — mission execution, launch cadence, and
  Tier-2 startup ecosystem.
- **`04_indianexpress_bengaluru_rail_clamped.json`** — illustrates the
  **confidence-clamp rule**. The article is genuinely ambiguous; the model
  returned `confidence < 0.5`, and the analyzer enforced
  `overall = neutral` with `score` bounded into `[-0.2, 0.2]`. Look at the
  `aspects` block to see the underlying tension that the polarity label
  (correctly) refuses to commit on: positive on commute benefits, negative on
  delivery timeline / disruption / land acquisition.

## Notes on provenance

These examples illustrate the schema and prompt behavior. The article URLs are
real publishers — The Hindu, Mint, The Indian Express — but any specific
article that was analyzed at a given moment may have moved or been updated
since. Re-running `/analyze` against a current URL on the same site will
produce a freshly generated structure of the same shape. If you re-run any of
these against the live API, your numeric fields (`tokens_used`, `analysis_ms`,
`mentions`, exact emotion intensities, `score` and `confidence`) will differ
from what's checked in here; that's expected.
