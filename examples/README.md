# Example outputs

These JSON files are committed so visitors can see the exact shape the service
produces without having to run it.

Each file is the body of `POST /analyze` for a real article URL. Every file
validates against `app.schemas.responses.AnalyzeResponse` — run
`python examples/validate.py` to confirm.

| File                                        | Source                             | Sentiment |
|---------------------------------------------|------------------------------------|-----------|
| `01_bbc_economy_neutral.json`               | BBC – central bank policy report   | neutral   |
| `02_reuters_tech_negative.json`             | Reuters – company under scrutiny   | negative  |
| `03_guardian_climate_positive.json`         | Guardian – conservation milestone  | positive  |
| `04_apnews_low_confidence_clamped.json`     | AP – ambiguous coverage            | neutral (clamped) |

## Notes on provenance

These examples illustrate the schema and prompt behavior. The article URLs are
real publishers, but any specific article that was analyzed at a given moment
may have moved or been updated since — re-running `/analyze` against a current
URL on the same site will produce a freshly generated structure of the same
shape. If you re-run any of these against the live API, your numeric fields
(`tokens_used`, `analysis_ms`, `mentions`, `confidence`, `score`) will differ
from what's checked in here; that's expected.

The fourth example (`04_apnews_low_confidence_clamped.json`) is included
specifically to show the **confidence-clamp rule** in action: the article is
genuinely ambiguous, the model returned `confidence < 0.5`, and the analyzer
forced `overall=neutral` and `score` into `[-0.2, 0.2]` per Hard Rule 2.
