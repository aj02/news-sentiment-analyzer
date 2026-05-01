# news-sentiment-analyzer

A small, production-style service that turns a news article URL (or an RSS feed)
into structured JSON: a neutral summary, sentiment with a confidence-aware
score, named entities, key claims tagged by stance, and topics.

It exists to demonstrate **applied AI infrastructure work** — the engineering
around LLM calls, not the LLM call itself: provider-swappable client,
schema-validated structured output, versioned prompts on disk, Redis caching,
retries with backoff, request-id-correlated logs, a multi-stage Docker build,
and a real test suite that mocks both HTTP and the model.

It is **not** a trading signal generator, a stock picker, or financial advice.
It analyzes article content. What you do with the JSON downstream is up to you.

---

## What it produces

A single article goes in, structured JSON comes out:

```json
{
  "url": "https://www.bbc.com/news/articles/example",
  "title": "Fed holds rates steady amid inflation progress",
  "published_at": "2026-04-30T14:30:00+00:00",
  "summary": "The Federal Reserve kept its benchmark rate unchanged at 4.25-4.5%. Chair Powell said the committee was 'in no hurry' to adjust policy and would be guided by incoming data on prices and the labor market.",
  "sentiment": {
    "overall": "neutral",
    "score": 0.0,
    "confidence": 0.85,
    "rationale": "Pure factual reporting of a policy decision; no evaluative language."
  },
  "entities": [
    { "name": "Federal Reserve", "type": "org", "sentiment": "neutral", "mentions": 2 },
    { "name": "Jerome Powell",   "type": "person", "sentiment": "neutral", "mentions": 1 }
  ],
  "key_claims": [
    { "claim": "The Fed held its benchmark rate at 4.25-4.5%.",        "stance": "asserted" },
    { "claim": "The committee is in no hurry to adjust policy.",       "stance": "reported" }
  ],
  "topics": ["monetary-policy", "federal-reserve"],
  "model_used": "claude-haiku-4-5",
  "tokens_used": 1843,
  "cached": false,
  "analysis_ms": 2104
}
```

See [`examples/`](examples/) for committed outputs.

---

## Why I built it

I wanted a small, self-contained codebase that shows how I think about wrapping
an LLM in a real service — the parts that aren't the prompt:

- A schema that's the same object on both sides of the wire (Pydantic → JSON
  schema → embedded in the prompt → parsed back into the same Pydantic model).
- Provider abstraction so swapping Anthropic ↔ OpenAI is one env var.
- Caching keyed by `prompt_version + model + sha256(url)` so prompt or model
  changes naturally invalidate stale entries.
- A confidence-clamp rule enforced both in the prompt **and** server-side,
  because LLMs occasionally ignore their own rules.
- Versioned prompts on disk (`app/prompts/v1/`, `app/prompts/v2/`) so iteration
  is reviewable.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FastAPI app                                │
│                                                                         │
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
  -d '{"url": "https://www.bbc.com/news/articles/example"}' | jq
```

### Run the tests

```bash
make test
```

The test suite is fully offline — `respx` mocks all HTTP, `fakeredis` mocks
Redis, and a `FakeLLMClient` returns canned JSON keyed by article URL.

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

The interesting work is in [`app/prompts/v2/system.txt.j2`](app/prompts/v2/system.txt.j2).
Version history lives in [`app/prompts/CHANGELOG.md`](app/prompts/CHANGELOG.md).

**Schema is the contract, not free-text instructions.** The `LLMAnalysis`
Pydantic model is rendered to a JSON schema and embedded in the system prompt
verbatim. The prompt loader and the validator share one source of truth: change
the model, the prompt picks it up; change the prompt, the validator still
catches drift. `extra="forbid"` on the model means hallucinated keys get
rejected loudly, which is how I want to find out about prompt regressions.

**Hard rules, not soft suggestions.** Five numbered rules in the system prompt:

1. **Don't invent facts.** Every claim, entity, and quote must trace back to
   the article text. Outside knowledge is excluded.
2. **Confidence < 0.5 forces neutral.** If the model is unsure, it can't
   commit to a sign. The prompt says so; the analyzer enforces it server-side
   too — the code is the receipt.
3. **No recommendations.** This is content analysis, not advice.
4. **Non-substantive content gets a graceful fallback** — empty entity/claim
   lists, neutral sentiment, confidence 0.0. Better than a 500.
5. **JSON only.** No prose, no markdown fences. The decoder is forgiving as
   defense-in-depth, but the prompt asks for the strict form.

**Few-shot examples cover the boundary cases.** Three examples in the prompt:
straight reporting (neutral), clearly evaluative coverage (negative), and a
low-confidence ambiguous case demonstrating Rule 2 in action. The third one
exists specifically to show the model the *desired* response when it's
tempted to commit too hard.

**Stance taxonomy is explicit.** `asserted` / `reported` / `speculated` —
defined inline so the model doesn't drift toward inventing custom labels. This
is the kind of distinction that's easy for a human and easy to lose in
freeform output.

**Versioning is git-visible.** v1 is the no-guardrails baseline, kept committed
so the diff to v2 shows what each rule was worth. New versions go in new
directories; bumping `PROMPT_VERSION` swaps them. The cache key includes the
prompt version, so flipping to v3 doesn't read v2's stale entries.

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

A back-of-the-envelope sketch — your mileage will depend on article length,
prompt revision, and provider price changes.

The system prompt (v2 with embedded schema and three examples) is roughly
**1,800 input tokens**. The user prompt is the article text itself; mainstream
news articles run **800–2,000 input tokens**. Output is bounded but typically
lands around **300–600 completion tokens** for a tight summary + entities +
claims block.

A representative single-article call:

| Phase           | Tokens (typical) |
|-----------------|-----------------:|
| System prompt   | ~1,800           |
| User article    | ~1,500           |
| Output          | ~450             |
| **Total**       | **~3,750**       |

For 1,000 articles (no caching benefit), at illustrative public list prices:

- **Claude Haiku 4.5** (input ~$1/MTok, output ~$5/MTok):
  `1000 × 3,300 input / 1M × $1 + 1000 × 450 output / 1M × $5` ≈ **$5.55**
- **Claude Sonnet 4.6** (input ~$3/MTok, output ~$15/MTok): ≈ **$16.65**
- **GPT-4o-mini** (input ~$0.15/MTok, output ~$0.60/MTok): ≈ **$0.77**
- **GPT-4o** (input ~$2.50/MTok, output ~$10/MTok): ≈ **$12.75**

Caching matters: re-analyzing the same URL is a Redis hit at zero LLM cost.
With a typical news-aggregation workload (re-pulls of the same RSS feed, retries
after transient failures), 30–60% of `/analyze` calls go to cache in practice.

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
│   ├── v2/          Current prompt — schema + few-shot + 5 hard rules
│   └── CHANGELOG.md
├── schemas/         Pydantic models — requests, responses, LLM output (LLMAnalysis)
├── services/
│   ├── analyzer.py  Orchestrator: fetch → cache → LLM → validate → cache → return
│   ├── cache.py     Redis wrapper. Key = nsa:{prompt}:{model}:{sha256(url)}
│   ├── fetcher.py   httpx + trafilatura + feedparser, with timeouts and byte caps
│   └── llm/         Provider abstraction (base.py, anthropic.py, openai.py)
└── main.py          App factory, lifespan-managed services, request-id middleware

tests/
├── fixtures/        Static HTML, RSS XML, canned LLM JSON
├── conftest.py      Real services + a FakeLLMClient + fakeredis
├── test_analyzer.py happy path, cache hit, force_refresh, LLM/schema failure, clamp
├── test_api.py      end-to-end through FastAPI TestClient
├── test_cache.py    round-trip, key namespacing, ping
├── test_fetcher.py  extraction, paywall, 404, RSS parse + limit
├── test_llm_base.py JSON decoder edge cases (fences, prose-around-JSON)
├── test_prompts.py  versions load, schema embedded, render shape
└── test_schemas.py  extra fields rejected, bounds enforced, enums enforced

examples/            Committed JSON outputs from real article URLs
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
- **No frontend.** It's a JSON API.

---

## License

MIT.
