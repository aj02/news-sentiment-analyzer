# news-sentiment-analyzer

A small, production-style service that turns an Indian news article URL (or
an RSS feed) into structured JSON: a neutral summary, multi-axis sentiment
(polarity + subjectivity + certainty + Plutchik emotions), aspect-level
sentiment per topic, attributed quotes with framing, named entities, key
claims tagged by stance, and topics.

It exists to demonstrate **applied AI infrastructure work** — the engineering
around LLM calls, not the LLM call itself: provider-swappable client,
schema-validated structured output, versioned prompts on disk, Redis caching,
retries with backoff, request-id-correlated logs, a multi-stage Docker build,
a real test suite that mocks both HTTP and the model, and a small dark-mode UI
that visualizes every dimension the analyzer extracts.

It is **not** a trading signal generator, a stock picker, or financial advice.
It analyzes article content. What you do with the JSON downstream is up to you.

---

## What it produces

A single article goes in, structured JSON comes out:

```jsonc
{
  "url": "https://www.thehindu.com/business/Economy/...",
  "title": "RBI holds repo rate at 6.50%, raises FY25 growth forecast to 7.2%",
  "published_at": "2026-04-30T11:30:00+00:00",
  "summary": "The RBI's MPC unanimously held the repo rate at 6.50% ...",
  "sentiment": {
    "overall": "neutral",
    "score": 0.05,
    "confidence": 0.85,
    "rationale": "Straight policy reporting with no evaluative framing.",
    "subjectivity": 0.10,           // 0 = factual, 1 = opinionated
    "certainty":    0.88,           // 0 = hedged,  1 = definitive
    "emotions": {                   // Plutchik 8, each in [0, 1]
      "joy": 0.10, "trust": 0.55, "fear": 0.20, "surprise": 0.10,
      "sadness": 0.0, "disgust": 0.0, "anger": 0.0, "anticipation": 0.50
    }
  },
  "entities": [
    { "name": "Reserve Bank of India", "type": "org", "sentiment": "neutral", "mentions": 4 },
    { "name": "Shaktikanta Das", "type": "person", "sentiment": "neutral", "mentions": 2 }
  ],
  "key_claims": [
    { "claim": "The MPC voted unanimously to hold the repo rate at 6.50%.", "stance": "asserted" },
    { "claim": "The committee is in no hurry to adjust policy.",            "stance": "reported" }
  ],
  "aspects": [
    { "aspect": "GDP growth",     "sentiment": "positive", "score":  0.45, "evidence": "FY25 growth forecast raised to 7.2% ..." },
    { "aspect": "monsoon risk",   "sentiment": "negative", "score": -0.30, "evidence": "Governor warned an uncertain monsoon ..." }
  ],
  "quotes": [
    {
      "text": "On a glide path to the 4% medium-term target.",
      "speaker": "Shaktikanta Das", "speaker_role": "RBI Governor",
      "sentiment": "positive", "framing": "supportive"
    }
  ],
  "topics": ["monetary-policy", "rbi", "inflation", "gdp-growth", "monsoon"],
  "model_used": "claude-haiku-4-5",
  "tokens_used": 3617,
  "cached": false,
  "analysis_ms": 2104
}
```

See [`examples/`](examples/) for committed outputs from real articles on The
Hindu, Mint, and The Indian Express.

---

## What's "advanced" about the sentiment analysis

Most LLM-based sentiment tools collapse an article into one label and a score.
This service produces six independent dimensions per article:

| Dimension                      | Range / shape           | What it captures                                                                 |
|--------------------------------|-------------------------|----------------------------------------------------------------------------------|
| `sentiment.overall` + `score`  | label + [-1, 1]         | Polarity — the article's tone toward its primary subject.                        |
| `sentiment.confidence`         | [0, 1]                  | Self-assessed certainty in the polarity label. < 0.5 forces label to neutral.    |
| `sentiment.subjectivity`       | [0, 1]                  | Factual reporting ↔ editorialized commentary. *Independent of polarity.*         |
| `sentiment.certainty`          | [0, 1]                  | Hedged ('could', 'may') ↔ stated as definite fact. *Independent of polarity.*    |
| `sentiment.emotions`           | 8 values, each [0, 1]   | Plutchik wheel — joy, trust, fear, surprise, sadness, disgust, anger, anticipation. |
| `aspects[]`                    | up to 8 items           | Aspect-based sentiment — per-topic polarity within the article.                  |
| `quotes[]`                     | up to 8 items           | Direct quotes with `speaker`, `speaker_role`, sentiment, and `framing`.          |

The interesting work is in surfacing the **second-order** structure that
single-label sentiment loses. An RBI policy piece can be `overall: neutral`
but contain `aspects: [GDP growth: positive, monsoon risk: negative]`. A
corporate-governance investigation can be `overall: negative` but with high
subjectivity — telling you *how* the article is negative, not just that it is.

The four committed examples in [`examples/`](examples/) walk through these
combinations.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FastAPI app                                │
│                                                                         │
│   GET /        UI (vanilla HTML, dark mode, no build step)              │
│   POST /analyze        POST /analyze/feed       GET /health  /ready     │
│        │                     │                                          │
│        └─────────────────────┴──────────────┐                           │
│                                             ▼                           │
│                                    ┌─────────────────┐                  │
│                                    │    Analyzer     │                  │
│                                    └────────┬────────┘                  │
│                                             │                           │
│      ┌─────────────────┬────────────────────┼────────────────────┐      │
│      ▼                 ▼                    ▼                    ▼      │
│  ┌─────────┐     ┌──────────┐         ┌─────────┐         ┌───────────┐ │
│  │ Fetcher │     │  Prompt  │         │   LLM   │         │   Cache   │ │
│  │ httpx + │     │  loader  │         │  client │         │  Redis    │ │
│  │trafil-  │     │ (Jinja2, │         │ Anthropic│        │ orjson    │ │
│  │atura +  │     │ versioned│         │ or OpenAI│        │           │ │
│  │feedparser│   │ on disk) │         └─────────┘         └───────────┘ │
│  └─────────┘     └──────────┘                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

Request lifecycle for `POST /analyze`:

1. **Bind a request_id** (from `X-Request-Id` header or generated). All logs in
   this request carry it.
2. **Cache lookup** — `nsa:{prompt_version}:{model}:{sha256(url)}`. Hit returns
   immediately; miss continues.
3. **Fetch** — `httpx.AsyncClient` with `FETCH_TIMEOUT_SECONDS` and a streaming
   max-bytes guard. Raises `FetchError` on non-2xx, timeout, or oversized body.
4. **Extract** — `trafilatura.extract` with `favor_recall=True`. If under
   `_MIN_ARTICLE_CHARS` (280) we assume paywall/JS-only and raise
   `UnsupportedContentError` (HTTP 422).
5. **Render prompt** — load the configured `PROMPT_VERSION` from disk; inject
   the `LLMAnalysis.model_json_schema()` so the prompt is always in sync with
   the validating model.
6. **Call LLM** — Anthropic or OpenAI behind the `LLMClient` interface. Tenacity
   wrapper: exponential backoff, retry only on transport / rate-limit / server
   errors. Per-call timeout from `LLM_TIMEOUT_SECONDS`.
7. **Parse + validate** — robust JSON decode (handles ```json fences and prose
   prefixes), then `LLMAnalysis.model_validate`. Schema mismatch → `LLMError`.
8. **Confidence clamp** — if the model returned `confidence < 0.5` but didn't
   move `overall` to `neutral`, the analyzer enforces the rule server-side. The
   prompt asks for it; the code guarantees it.
9. **Cache write** — set with `CACHE_TTL_SECONDS`. A Redis outage logs a
   warning but does not fail the request.
10. **Return** — `AnalyzeResponse` with `model_used`, `tokens_used`, `cached`,
    `analysis_ms`. The middleware echoes back `x-request-id`.

---

## Quick start

```bash
git clone https://github.com/aj02/news-sentiment-analyzer.git
cd news-sentiment-analyzer
```

### Local (uvicorn + local Redis)

```bash
cp .env.example .env
# Set ANTHROPIC_API_KEY (or switch to OPENAI_API_KEY + LLM_PROVIDER=openai)
make install
docker run -d --rm --name nsa-redis -p 6379:6379 redis:7-alpine
make run
```

### Docker compose

```bash
cp .env.example .env
# Set your API key in .env
make docker-up
```

Either way, hit it:

```bash
curl -s -X POST http://localhost:8000/analyze \
  -H "content-type: application/json" \
  -d '{"url":"https://www.thehindu.com/business/Economy/<some-article>"}' | jq
```

Or just open **http://localhost:8000/** in a browser — there's a dark-mode UI
with sentiment bars, an emotion grid, an aspects list, and quote cards.

### Run the tests

```bash
make test
```

The test suite is fully offline — `respx` mocks all HTTP, `fakeredis` mocks
Redis, and a `FakeLLMClient` returns canned JSON keyed by article URL.

---

## Indian RSS feeds — try these in the UI's "RSS Feed" tab

The UI's feed tab has quick-shortcuts for these. Feed URLs do change
occasionally — check the publisher's feed page if any of these break.

| Source              | Section                  | Feed URL                                                                  |
|---------------------|--------------------------|---------------------------------------------------------------------------|
| The Hindu           | Economy                  | `https://www.thehindu.com/business/Economy/feeder/default.rss`            |
| The Hindu           | National                 | `https://www.thehindu.com/news/national/feeder/default.rss`               |
| The Hindu           | Sci-Tech                 | `https://www.thehindu.com/sci-tech/feeder/default.rss`                    |
| Mint                | Top news                 | `https://www.livemint.com/rss/news`                                       |
| Mint                | Markets                  | `https://www.livemint.com/rss/markets`                                    |
| Mint                | Companies                | `https://www.livemint.com/rss/companies`                                  |
| Economic Times      | Top stories              | `https://economictimes.indiatimes.com/rssfeedstopstories.cms`             |
| Economic Times      | Markets                  | `https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms`    |
| NDTV                | Top stories              | `https://feeds.feedburner.com/ndtvnews-top-stories`                       |
| NDTV                | Business                 | `https://feeds.feedburner.com/ndtvprofit-latest`                          |
| The Indian Express  | India                    | `https://indianexpress.com/section/india/feed/`                           |
| The Indian Express  | Business                 | `https://indianexpress.com/section/business/feed/`                        |
| Times of India      | Top stories              | `https://timesofindia.indiatimes.com/rssfeedstopstories.cms`              |
| News18              | India                    | `https://www.news18.com/rss/india.xml`                                    |
| Scroll.in           | All                      | `https://feeds.feedburner.com/Scroll`                                     |
| The Wire            | All                      | `https://thewire.in/rss`                                                  |
| Hindustan Times     | India News               | `https://www.hindustantimes.com/feeds/rss/india-news/index.xml`           |

**Caveat on paywalled outlets.** Some Indian outlets (Mint behind certain
sections, ET Prime, BS Premium) serve a paywall stub to unauthenticated
fetchers. The analyzer detects this — extracted text < 280 chars triggers
`unsupported_content` (HTTP 422) instead of feeding garbage to the LLM. You'll
see this cleanly in the UI as a structured error panel.

---

## API

### `POST /analyze`

```jsonc
// request
{ "url": "https://...", "force_refresh": false }
```

Returns the `AnalyzeResponse` object shown at the top of this README.

### `POST /analyze/feed`

```jsonc
// request
{ "feed_url": "https://...", "limit": 10, "force_refresh": false }
```

Returns:

```jsonc
{
  "feed_url": "...",
  "feed_title": "...",
  "items_attempted": 10,
  "items_succeeded": 9,
  "results": [
    { "analysis": { /* AnalyzeResponse */ } },
    { "error":    { "url": "...", "error_code": "fetch_failed", "error_message": "..." } }
  ]
}
```

Per-item failures don't fail the whole batch — you get partial results.

### `GET /health`

Liveness — returns `{"status": "ok", "version": "0.1.0"}` without touching
Redis or any external dep.

### `GET /ready`

Readiness — pings Redis. Returns `redis: "ok" | "disabled" | "down: <detail>"`.
Use this from your orchestrator.

### `GET /`

Serves the dark-mode UI from `app/static/index.html`. No build step,
no JS framework.

### Errors

All errors return a stable JSON envelope:

```jsonc
{
  "error": "fetch_failed",        // stable machine code
  "message": "Upstream returned HTTP 404",
  "detail": "article fetch: https://...",
  "request_id": "f3c2..."
}
```

| `error`                 | HTTP | Meaning                                                      |
|-------------------------|-----:|--------------------------------------------------------------|
| `invalid_request`       | 422  | Body failed Pydantic validation                              |
| `fetch_failed`          | 502  | Network failure / non-2xx / oversized response               |
| `unsupported_content`   | 422  | Fetched OK but no extractable article text (paywall, JS-only)|
| `rss_parse_failed`      | 422  | Feed body is not parseable RSS/Atom                          |
| `llm_failed`            | 502  | LLM call failed after retries OR returned invalid output     |
| `internal_error`        | 500  | Unhandled exception                                          |

---

## Prompt design notes

The interesting work is in [`app/prompts/v3/system.txt.j2`](app/prompts/v3/system.txt.j2).
Version history lives in [`app/prompts/CHANGELOG.md`](app/prompts/CHANGELOG.md).

**Schema is the contract, not free-text instructions.** The `LLMAnalysis`
Pydantic model is rendered to a JSON schema and embedded in the system prompt
verbatim. The prompt loader and the validator share one source of truth: change
the model, the prompt picks it up; change the prompt, the validator still
catches drift. `extra="forbid"` on the model means hallucinated keys get
rejected loudly, which is how I want to find out about prompt regressions.

**Hard rules, not soft suggestions.** Six numbered rules in the v3 system prompt:

1. **Don't invent facts.** Every claim, entity, quote, and aspect must trace
   back to the article text. Outside knowledge is excluded.
2. **Confidence < 0.5 → neutral.** If the model is unsure about polarity, it
   can't commit to a sign. The prompt says so; the analyzer enforces it
   server-side too — the code is the receipt. Note: this rule applies only to
   `sentiment.overall` / `sentiment.score`, NOT to subjectivity, certainty, or
   emotions.
3. **No recommendations.** This is content analysis, not advice.
4. **Non-substantive content gets a graceful fallback** — empty entity / claim
   / aspect / quote lists, neutral polarity with confidence 0.0, all emotions
   at 0.0, subjectivity and certainty at 0.5.
5. **JSON only.** No prose, no markdown fences. The decoder is forgiving as
   defense-in-depth, but the prompt asks for the strict form.
6. **Independence of axes.** Subjectivity and certainty are NOT shortcuts for
   sentiment. A negative article can be highly factual (low subjectivity, high
   certainty) AND a positive article can be highly speculative.

**Few-shot examples cover the boundary cases — in Indian context.** Three
examples in the v3 prompt:

- **Neutral, factual, high certainty** — RBI MPC holding the repo rate.
- **Negative, moderate subjectivity, multiple aspects** — A Mint-style
  corporate-governance investigation at a fictional Indian listed company.
- **Low-confidence ambiguous** — Bengaluru Suburban Rail groundbreaking, where
  Hard Rule 2 is shown clamping the polarity label.

Each demonstrates the *desired* response when the model is tempted to
over-claim, including emotion intensities, aspect breakdowns, and quote
framings.

**Stance and framing taxonomies are explicit.** Claims use
`asserted` / `reported` / `speculated`; quote framings use `supportive` /
`neutral` / `skeptical` — both defined inline so the model doesn't drift
toward inventing custom labels.

**Versioning is git-visible.**
- **v1** is the no-guardrails baseline, kept committed so the diff to v2/v3
  shows what each rule was worth.
- **v2** added few-shot examples and the confidence-clamp rule (US-context
  examples).
- **v3** (current) adds subjectivity, certainty, emotions, aspects, and quotes,
  and reworks all examples to Indian context.

The cache key includes the prompt version, so flipping `PROMPT_VERSION`
doesn't read the previous version's stale entries.

---

## Swapping LLM providers

Two env vars:

```bash
LLM_PROVIDER=openai    # was: anthropic
LLM_MODEL=gpt-4o-mini  # was: claude-haiku-4-5
```

Both providers receive the same system + user messages. OpenAI gets
`response_format={"type":"json_object"}` for an extra JSON guarantee; Anthropic
relies on prompt instruction plus the robust JSON decoder in
[`app/services/llm/base.py`](app/services/llm/base.py).

Adding a third provider means subclassing `LLMClient`, returning an `LLMResult`,
and registering it in [`app/services/llm/factory.py`](app/services/llm/factory.py).
Roughly 70 lines for a complete implementation — see
[`anthropic.py`](app/services/llm/anthropic.py) or
[`openai.py`](app/services/llm/openai.py).

---

## Cost estimation per 1,000 articles

A back-of-the-envelope sketch. The v3 prompt is richer than v2, so input and
output token counts are higher.

The v3 system prompt (with embedded schema and three Indian-context
few-shot examples) is roughly **3,200 input tokens**. The user prompt is the
article text itself; mainstream Indian news articles run **800–2,200 input
tokens**. Output is bounded but typically lands around **600–1,000 completion
tokens** for the full v3 structure (sentiment + 4 axes + emotions + aspects +
quotes + entities + claims + topics).

A representative single-article call under v3:

| Phase           | Tokens (typical) |
|-----------------|-----------------:|
| System prompt   | ~3,200           |
| User article    | ~1,500           |
| Output          | ~800             |
| **Total**       | **~5,500**       |

For 1,000 articles (no caching benefit), at illustrative public list prices
(re-derive against current pricing — these were the rough USD numbers
mid-2026):

- **Claude Haiku 4.5** (input ~$1/MTok, output ~$5/MTok):
  `1000 × 4,700 input / 1M × $1 + 1000 × 800 output / 1M × $5` ≈ **$8.70**
  (≈ ₹720 at ₹83/USD)
- **Claude Sonnet 4.6** (input ~$3/MTok, output ~$15/MTok): ≈ **$26.10** (≈ ₹2,160)
- **GPT-4o-mini** (input ~$0.15/MTok, output ~$0.60/MTok): ≈ **$1.18** (≈ ₹98)
- **GPT-4o** (input ~$2.50/MTok, output ~$10/MTok): ≈ **$19.75** (≈ ₹1,640)

The v3 schema is roughly **40–50% more expensive per call** than v2 (one extra
axis block + two extra arrays + larger few-shot context). Whether that's worth
it depends entirely on whether you actually use `aspects` and `quotes`
downstream. If you do, the extra cost replaces a separate aspect-extraction
pipeline. If you don't, set `PROMPT_VERSION=v2` to fall back.

Caching matters: re-analyzing the same URL is a Redis hit at zero LLM cost.
With a typical news-aggregation workload (re-pulls of the same RSS feed,
retries after transient failures), 30–60% of `/analyze` calls go to cache in
practice.

These numbers are **sketches** — re-derive against current pricing and your
actual article distribution before quoting them anywhere it matters.

---

## Layout

```
app/
├── api/             FastAPI routes, dependency providers, error handlers
├── core/            Settings (Pydantic Settings v2), structlog setup, exceptions
├── prompts/
│   ├── v1/          Baseline prompt — no few-shot, no guardrails (kept for diff)
│   ├── v2/          Polarity-only with confidence clamp, US-context examples
│   ├── v3/          Current — polarity + subjectivity/certainty/emotions + aspects + quotes,
│   │                Indian-context few-shot examples
│   └── CHANGELOG.md
├── schemas/         Pydantic models — requests, responses, LLM output (LLMAnalysis)
├── services/
│   ├── analyzer.py  Orchestrator: fetch → cache → LLM → validate → cache → return
│   ├── cache.py     Redis wrapper. Key = nsa:{prompt}:{model}:{sha256(url)}
│   ├── fetcher.py   httpx + trafilatura + feedparser, with timeouts and byte caps
│   └── llm/         Provider abstraction (base.py, anthropic.py, openai.py)
├── static/          Single-file dark-mode UI (no build step)
└── main.py          App factory, lifespan-managed services, request-id middleware

tests/
├── fixtures/        Static HTML, RSS XML, canned LLM JSON (Indian-context, v3 schema)
├── conftest.py      Real services + a FakeLLMClient + fakeredis
├── test_analyzer.py happy path, cache hit, force_refresh, LLM/schema failure, clamp
├── test_api.py      end-to-end through FastAPI TestClient
├── test_cache.py    round-trip, key namespacing, ping
├── test_fetcher.py  extraction, paywall, 404, RSS parse + limit
├── test_llm_base.py JSON decoder edge cases (fences, prose-around-JSON)
├── test_prompts.py  versions load, schema embedded, render shape
└── test_schemas.py  v2 invariants + v3 axes/aspects/quotes validation

examples/            Committed JSON outputs from real Indian news article URLs
```

---

## Deliberately out of scope

- **No trading / financial signals.** The output is content analysis only.
- **No auth.** Run it behind your own gateway.
- **No background workers / queues.** `/analyze` is sync; for high-throughput
  use you'd front it with a worker pool or run replicas.
- **No accuracy benchmarks.** I haven't measured sentiment accuracy against a
  labeled corpus and I won't claim numbers I haven't validated.
- **No fine-tuning.** Pure prompt engineering on top of frontier models.
- **No multilingual analysis (yet).** Articles in Hindi / Tamil / Bengali etc.
  will be analyzed in their original language by the LLM, but the prompt and
  few-shot examples are English; quality for non-English content is untested.

---

## License

MIT.
