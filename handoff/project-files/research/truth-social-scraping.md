# Free ways to get Trump's Truth Social posts (replacing ScrapeCreators)

Research for stage 1 (brainstorm), 2026-09-30. Desk research only: this session's network
policy blocks `truthsocial.com`, `trumpstruth.org` and `ix.cnn.io`, so **no latency or
blocking numbers below were measured by us**. Where a figure comes from a source it is cited;
where it is my inference it says so.

## What the replacement has to do
`shitposts/truth_social_s3_harvester.py` implements `SignalHarvester`: `_test_connection`,
`_fetch_batch(cursor)` and three extractors (`id`, `created_at`, `content`). Anything below can
slot in as a new harvester class as long as it maps to the same raw JSON shape
(Mastodon-style status: `id`, `created_at`, `content`, engagement counts, `reblog`, media).

## Two facts that frame everything
1. **Truth Social now sells the fast path.** Since Aug 2026 TMTG sells a machine-readable
   feed of Trump's and other top accounts' posts to trading firms, reportedly at
   $60k to $100k a month with millisecond delivery
   ([ABC](https://www.abc.net.au/news/2026-08-11/donald-trump-sells-early-access-to-truth-social-posts/107015908),
   [Axios](https://www.axios.com/2026/07/16/truth-social-license-data-wall-street)). Its CEO said
   firms scraping the site "in violation of its terms" should expect "a lot of friction".
   A free source will never be first; our realistic target is "a few minutes after the post".
   Inference: that is fine for our T+1h..T+30d outcome windows, not for sub-minute trading.
2. **The ToS bans what we'd be doing directly.** Sections 7.1, 7.6, 7.9 and 7.22 prohibit
   bots, scrapers and systematic retrieval, and 7.14 bans revenue-generating use
   ([ToS](https://help.truthsocial.com/legal/terms-of-service/)). ScrapeCreators is itself a
   scraper, so today's setup already carries this exposure one step removed.

## Options compared

| Option | Latency (post to us) | Reliability / blocking | Limits | ToS / legal | Cost |
|---|---|---|---|---|---|
| **A. Direct public API** (`truthsocial.com/api/v1/accounts/107780257626128497/statuses`, Mastodon-compatible) | Best case ~poll interval (30-60 s). Unmeasured. | Cloudflare blocks non-browser and cloud IPs; Error 1015 after ~40 rapid requests ([truthbrush #45](https://github.com/stanfordio/truthbrush/issues/45)). RSSHub gave up on it ([#20986](https://github.com/DIYgod/RSSHub/issues/20986)). Railway is a datacenter IP, so expect blocks. | Header limit 300 req per window ([truthbrush api.py](https://github.com/stanfordio/truthbrush/blob/main/truthbrush/api.py)) | Direct breach of 7.6/7.9/7.22; TMTG actively hostile | Free, plus a residential proxy if blocked (not free) |
| **B. truthbrush** (Python client, curl_cffi Chrome impersonation) | Same as A | Same as A. Stanford archived it Apr 2026; fork at [w2rc/truthbrush](https://github.com/w2rc/truthbrush). `pull_statuses` needs a logged-in account. | Same as A | Same as A, plus a Truth Social account tied to the scraping | Free |
| **C. CNN archive JSON** (`ix.cnn.io/data/truth-social/truth_archive.json`, also CSV/Parquet) | Updated "every five minutes" ([stiles README](https://github.com/stiles/trump-truth-social-archive/blob/main/README.md)), so ~2-7 min worst case after our poll (inference) | Plain static file, no auth ([truthsocial-archiver](https://github.com/mickpletcher/truthsocial-archiver)). Single upstream we don't control; could stop or change without notice. | None stated; one small GET per minute is polite (inference) | We never touch Truth Social. No published reuse terms from CNN; fine for internal research, ask before redistributing | Free |
| **D. trumpstruth.org RSS** (`trumpstruth.org/feed`) | Site "checks for new posts every few minutes" ([FAQ](https://www.trumpstruth.org/faq)) | Public RSS, no auth; used as primary source by other bots ([trump-truthsocial-catalyst](https://github.com/yan-labs/trump-truthsocial-catalyst)). One RSSHub comment says the fallback "doesn't work anymore" (unverified). Run by Defending Democracy Together. | None stated | Same as C; no stated terms | Free |
| **E. Paid scrapers** (Apify actors, ScrapeCreators today) | Depends on our poll rate | Residential proxy rotation handles Cloudflare | Per-result pricing | Same ToS exposure, via the vendor | Apify ~$0.0023/post ([automation-lab](https://apify.com/automation-lab/truth-social-scraper)); not free |
| **F. Official TMTG API** | Milliseconds | Contractual | Contractual | Clean | $60k-100k/month. Out of budget. |

Not viable: native Mastodon RSS (`@user.rss`) is not served by Truth Social as far as any source
shows; RSSHub has no Truth Social route; Nitter-style mirrors don't exist for it.

## Recommendation
**Build a mirror-based harvester (C + D) now; treat direct access (A) as an optional fast path
that Chris decides on after a live test.**

- New `TruthSocialMirrorHarvester` polls the CNN JSON and the trumpstruth RSS every 60 s,
  dedupes on the Truth Social status ID, and writes the same raw shape to S3. Two independent
  mirrors cover each other's outages. Cost $0, no Truth Social account, no Cloudflare fight,
  and no direct ToS breach by us.
- Expected latency 1-7 min post-to-S3 (inference, needs measuring). That is dwarfed today by
  the pipeline's own ~25 min of stacked cron waits, so the bigger latency win is in the
  pipeline, not the scraper.
- Keep ScrapeCreators wired as a paid fallback until the mirrors have a clean week, then drop it.
- Engagement counts: the CNN file reportedly carries reply/reblog/favourite counts (stiles'
  schema); the RSS will not. Counts captured at harvest time were low-value anyway.

**Direct API (A/B) only if Chris accepts the ToS risk.** It is the only free route to
sub-minute latency, but it breaches the ToS, Railway IPs are likely blocked, and TMTG says it
will add friction. If wanted, test it read-only from Railway first, never from a personal account.

## How to measure it
Sandbox results go through Anthropic's proxy and say nothing about Truth Social blocking, so
the proof has to run on Railway. A read-only probe that polls all sources once a minute and logs
first-seen time per status ID is ready in `research/probe/` (see its README); it runs as a
temporary, separate Railway service once Chris picks how to deploy it.
