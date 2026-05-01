"""Static HTML fixtures used to test the fetcher + extractor without network."""

from __future__ import annotations

FED_RATES_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Fed holds rates steady</title>
  <meta property="article:published_time" content="2026-04-30T14:30:00Z">
</head>
<body>
<article>
<h1>Fed holds rates steady amid inflation progress</h1>
<p>WASHINGTON — The Federal Reserve held its benchmark interest rate steady on Wednesday at a range
of 4.25% to 4.5%, citing continued progress on inflation. The decision was unanimous.</p>
<p>Chair Jerome Powell said in a press conference following the meeting that the committee was "in
no hurry to adjust policy" and would continue to monitor incoming data on prices and the labor
market before considering changes.</p>
<p>The central bank's preferred measure of inflation has cooled meaningfully over the past year,
though it remains above the Fed's 2% target. Powell emphasized that the path forward would be
shaped entirely by data rather than calendar-based expectations.</p>
<p>Markets responded with little movement. The S&amp;P 500 closed roughly flat on the day, while
the yield on the 10-year Treasury note edged slightly lower.</p>
<p>Economists surveyed before the meeting had widely expected the Fed to hold. Attention now
turns to the next set of inflation prints due later this month, which will inform the committee's
discussions at the next scheduled meeting.</p>
</article>
</body>
</html>
"""

# Just under the extraction threshold — used to verify UnsupportedContentError fires.
PAYWALL_STUB_HTML = """\
<!DOCTYPE html>
<html><head><title>Paywalled</title></head>
<body><p>Subscribe to read.</p></body></html>
"""

RSS_FEED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Test News Feed</title>
  <link>https://example.test/feed</link>
  <description>Test feed for unit tests</description>
  <item>
    <title>Fed holds rates steady amid inflation progress</title>
    <link>https://example.test/articles/fed-rates</link>
    <pubDate>Wed, 30 Apr 2026 14:30:00 GMT</pubDate>
    <description>Fed kept rates at 4.25-4.5%</description>
  </item>
  <item>
    <title>GreenLine breaks ground</title>
    <link>https://example.test/articles/greenline</link>
    <pubDate>Tue, 29 Apr 2026 09:00:00 GMT</pubDate>
    <description>Public reaction mixed.</description>
  </item>
</channel>
</rss>
"""

GREENLINE_HTML = """\
<!DOCTYPE html>
<html><head><title>GreenLine breaks ground</title></head>
<body><article>
<h1>GreenLine transit project breaks ground</h1>
<p>The new GreenLine transit project broke ground today in a ceremony attended by city officials.
Mayor Anya Patel called the project a milestone for regional transportation, saying it would shave
twenty minutes off many commutes when service begins in 2029.</p>
<p>Local residents quoted in interviews following the ceremony were divided. Some praised the
expected commute-time improvements. Others worried about the next several years of construction
noise, dust, and street closures along the route.</p>
<p>Construction is expected to last roughly four years. The project's total budget is $1.2 billion,
funded through a mix of federal grants and a regional transit bond approved by voters in 2024.</p>
<p>Officials noted that environmental review of the route is complete and that early-stage utility
relocation work has already begun in the corridor's eastern segment.</p>
</article></body>
</html>
"""

FEED_WITH_BROKEN_ITEM_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Partially Broken Feed</title>
  <link>https://example.test/feed-with-broken</link>
  <description>One good item, one item that 503s</description>
  <item>
    <title>Fed holds rates steady amid inflation progress</title>
    <link>https://example.test/articles/fed-rates</link>
    <pubDate>Wed, 30 Apr 2026 14:30:00 GMT</pubDate>
  </item>
  <item>
    <title>Server error</title>
    <link>https://example.test/articles/server-error</link>
    <pubDate>Tue, 29 Apr 2026 09:00:00 GMT</pubDate>
  </item>
</channel>
</rss>
"""

ARTICLES_BY_URL = {
    "https://example.test/articles/fed-rates": (FED_RATES_HTML, "text/html"),
    "https://example.test/articles/greenline": (GREENLINE_HTML, "text/html"),
    "https://example.test/articles/paywall": (PAYWALL_STUB_HTML, "text/html"),
    "https://example.test/feed": (RSS_FEED_XML, "application/rss+xml"),
    "https://example.test/feed-with-broken": (FEED_WITH_BROKEN_ITEM_XML, "application/rss+xml"),
}
