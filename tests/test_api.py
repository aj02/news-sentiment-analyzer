"""End-to-end via FastAPI TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_ready(client: TestClient):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["redis"] == "ok"
    assert body["status"] == "ok"


def test_analyze_happy_path(client: TestClient):
    r = client.post(
        "/analyze",
        json={"url": "https://example.test/articles/rbi-policy"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sentiment"]["overall"] == "neutral"
    assert body["cached"] is False
    assert body["tokens_used"] == 300
    assert "x-request-id" in r.headers


def test_analyze_invalid_url(client: TestClient):
    r = client.post("/analyze", json={"url": "not a url"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "invalid_request"


def test_analyze_extra_field_rejected(client: TestClient):
    r = client.post(
        "/analyze",
        json={"url": "https://example.test/articles/rbi-policy", "secret_flag": True},
    )
    assert r.status_code == 422


def test_analyze_fetch_404_returns_502(client: TestClient):
    r = client.post(
        "/analyze",
        json={"url": "https://example.test/articles/missing"},
    )
    assert r.status_code == 502
    body = r.json()
    assert body["error"] == "fetch_failed"


def test_analyze_paywall_returns_422(client: TestClient):
    r = client.post(
        "/analyze",
        json={"url": "https://example.test/articles/paywall"},
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "unsupported_content"


def test_analyze_feed(client: TestClient):
    r = client.post(
        "/analyze/feed",
        json={"feed_url": "https://example.test/feed", "limit": 10},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["feed_title"] == "Indian Economy News"
    assert body["items_attempted"] == 2
    assert body["items_succeeded"] == 2
    overalls = [r["analysis"]["sentiment"]["overall"] for r in body["results"]]
    assert "neutral" in overalls


def test_request_id_propagates(client: TestClient):
    r = client.get("/health", headers={"x-request-id": "test-rid-123"})
    assert r.headers["x-request-id"] == "test-rid-123"
