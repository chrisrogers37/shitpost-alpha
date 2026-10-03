# Test fixtures

Recorded from the sandbox on 2 Oct 2026, then trimmed:

- `cnn_head.json`: the first 12 KB of a real 32 KB range read of CNN's archive
  (`Range: bytes=0-32767`, answered 206). It ends part way through an object, as a range
  read does.
- `trumpstruth_feed.xml`: a real `www.trumpstruth.org/feed?t=...` answer cut to 7 of its
  100 items. The last item is reconstructed in the same shape (marked in the file):
  117307289681145880, whose text is a link to another Trump post (117304284426928910). It
  had left the feed's window when this was recorded.
- `archive_cc0_slice.json`, `archive_cnn_slice.json`: real items from the CC0 copy of the
  archive (github.com/stiles/trump-truth-social-archive) and CNN's live file, picked to
  cover a repost of each style, a media-only post, a bare-link quote, mojibake and HTML
  entities. The two slices overlap on two posts.

Hand-built, **unverified until PR 7 records real answers on Railway** (the sandbox never
calls Truth Social or ScrapeCreators):

- `direct_statuses.unverified.json`: Mastodon statuses as Truth Social's API returns them:
  a post, a repost, a reply, a media-only post and a quote.
- `scrapecreators_posts.unverified.json`: ScrapeCreators' `{"success": true, "posts": [...]}`
  around the same five statuses.
- `challenge.unverified.html`: a Cloudflare challenge page.

Recorded from Alpaca's market data API (`data.alpaca.markets`) on 2 Oct 2026, then
trimmed. The repo is public and Alpaca's data stays private, so every number in a bar
(`o`, `h`, `l`, `c`, `v`, `n`, `vw`) is a stand-in of the same type (100, 101, ... by bar);
keys, bar times, page tokens, statuses, rate-limit headers and error text are Alpaca's.
No request headers were kept.

- `alpaca_stock_bars_page1.json`, `alpaca_stock_bars_page2.json`: SPY daily bars for
  2024-01-02 to 2024-01-04, asked with `limit=2` so the answer comes in two pages joined
  by `next_page_token`.
- `alpaca_coin_bars.json`: BTC/USD daily bars asked from 2024-01-02 to 2024-01-03 (two
  bars: one starts exactly at `end`).
- `alpaca_error.json`: the 403 body for SIP data under 15 minutes old.
- `alpaca_claims/`: one recorded call per claim in engine/README.md ("Alpaca claims"):
  `recorded_at`, the request's path and parameters, the status, the rate-limit headers and
  the body. Long answers keep their first three and last two bars, with `bars_returned`
  giving the full count. In `f_nvda_split_raw.json` each stand-in price is the matching
  `f_nvda_split_all.json` stand-in times that day's real ratio of raw to adjusted close,
  rounded to two places (10.03 before the split, 1.00 after).
