"""Static HTML fixtures used to test the fetcher + extractor without network."""

from __future__ import annotations

RBI_POLICY_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>RBI holds repo rate steady at 6.50%</title>
  <meta property="article:published_time" content="2026-04-30T11:30:00+05:30">
</head>
<body>
<article>
<h1>RBI holds repo rate at 6.50%, raises FY25 growth forecast to 7.2%</h1>
<p>MUMBAI — The Reserve Bank of India's Monetary Policy Committee on Friday voted unanimously
to keep the repo rate unchanged at 6.50%, maintaining its 'withdrawal of accommodation' stance
for a sixth consecutive meeting.</p>
<p>Governor Shaktikanta Das said retail inflation, which eased to 4.83% in April, remained on a
'glide path' to the 4% medium-term target but warned that food price volatility from an uncertain
monsoon could disrupt that trajectory.</p>
<p>The MPC raised its FY25 GDP growth forecast to 7.2% from 7.0%, citing strong rural demand
recovery and a pickup in private capex. Markets responded with little movement; the Sensex closed
roughly flat on the day, while the 10-year G-Sec yield edged slightly lower.</p>
<p>Economists surveyed before the meeting had widely expected the hold. Attention now turns to
the next CPI print due later this month, which will inform the committee's discussions at the
August meeting.</p>
</article>
</body>
</html>
"""

# Just under the extraction threshold — used to verify UnsupportedContentError fires.
PAYWALL_STUB_HTML = """\
<!DOCTYPE html>
<html><head><title>Subscribe to read</title></head>
<body><p>Subscribe to read this article.</p></body></html>
"""

RSS_FEED_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>Indian Economy News</title>
  <link>https://example.test/feed</link>
  <description>Test feed for unit tests</description>
  <item>
    <title>RBI holds repo rate at 6.50%, raises FY25 growth forecast to 7.2%</title>
    <link>https://example.test/articles/rbi-policy</link>
    <pubDate>Fri, 30 Apr 2026 06:00:00 GMT</pubDate>
    <description>MPC unanimous on hold; growth forecast raised.</description>
  </item>
  <item>
    <title>Bengaluru Suburban Rail Project breaks ground at Yelahanka</title>
    <link>https://example.test/articles/bengaluru-rail</link>
    <pubDate>Tue, 29 Apr 2026 09:00:00 GMT</pubDate>
    <description>Construction begins after a decade of delays.</description>
  </item>
</channel>
</rss>
"""

BENGALURU_RAIL_HTML = """\
<!DOCTYPE html>
<html><head><title>Bengaluru Suburban Rail breaks ground</title></head>
<body><article>
<h1>Bengaluru Suburban Rail Project breaks ground at Yelahanka after a decade of delays</h1>
<p>The much-delayed Bengaluru Suburban Rail Project broke ground on Tuesday at Yelahanka station,
ten years after it was first announced. Karnataka Chief Minister Siddaramaiah called the start
of work 'long overdue' and said it would 'transform mobility' for IT corridor commuters.</p>
<p>Residents along the planned route gave The Hindu mixed reactions. Some welcomed faster
commutes once service begins in 2029, while others worried about three years of construction
noise and uncertainty about land acquisition compensation.</p>
<p>The first phase of the project, totalling 148 km of track across four corridors, is being
funded jointly by the Centre and the state government, alongside a multilateral loan from the
Asian Development Bank. Officials said environmental clearances are complete and early-stage
utility relocation has already begun in the eastern segment.</p>
<p>Construction is expected to last roughly four years. The total project budget stands at
₹15,767 crore.</p>
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
    <title>RBI holds repo rate at 6.50%</title>
    <link>https://example.test/articles/rbi-policy</link>
    <pubDate>Fri, 30 Apr 2026 06:00:00 GMT</pubDate>
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
    "https://example.test/articles/rbi-policy": (RBI_POLICY_HTML, "text/html"),
    "https://example.test/articles/bengaluru-rail": (BENGALURU_RAIL_HTML, "text/html"),
    "https://example.test/articles/paywall": (PAYWALL_STUB_HTML, "text/html"),
    "https://example.test/feed": (RSS_FEED_XML, "application/rss+xml"),
    "https://example.test/feed-with-broken": (FEED_WITH_BROKEN_ITEM_XML, "application/rss+xml"),
}
