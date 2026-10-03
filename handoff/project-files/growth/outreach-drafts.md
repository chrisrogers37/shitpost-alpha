# Outreach drafts: CNN and trumpstruth.org (Alpaca dropped)

Owner: thread "Plan growth and revenue". These are drafts for Chris to send himself or approve word for word, through the coordinator. Nothing here has been sent.

When to send:
- CNN and trumpstruth: before engine PR 2.
- Alpaca: DROPPED. Chris chose not to ask on 2 October: "if we get more official we pay". Don't send section 3; it's kept only for reference.

Placeholders in [brackets] are for Chris to fill in. Each answer goes into the terms register in the growth plan, with the date.

Poll intervals come from the 24-hour Railway test: CNN every 20 seconds, trumpstruth every 60 seconds. The engine plan may set different ones, so check with the engine planner before sending.

---

## 1. CNN (the Truth Social archive and its live JSON file)

To: the maintainer of github.com/stiles/trump-truth-social-archive, or CNN's data or permissions desk if he points elsewhere.

Subject: Permission to read your Truth Social JSON feed for a public market-research tracker

Hi,

I run Shitpost Alpha, an open-source project (github.com/chrisrogers37/shitpost-alpha) that tracks how markets move after Trump's Truth Social posts and grades each call in public.

We'd like to use two things of yours, with your permission:
1. The archive on GitHub, up to October 2025, for our historical backtest. We understand it's CC0, and we'll credit it.
2. The live JSON file the archive is built from (ix.cnn.io). We would read it no more than once every [20] seconds to detect new posts.

How we'd use the live file:
- We never republish it, and we never show a post's full text. Public pages quote at most about 200 characters and link to the original on Truth Social.
- What we publish is our own analysis: the % move in related tickers at fixed windows after the post, compared with SPY.
- The service is free today. Later we may charge for tools such as filters and webhooks. If we do, we'd only rely on your feed if that commercial use is fine with you.

Could you tell us whether this use is OK, whether you'd like a particular credit line or polling limit, and whether there are terms we should read? If you'd rather we didn't use the live file, we'll switch it off.

Thanks,
[Your name]
Shitpost Alpha · [contact email]

---

## 2. trumpstruth.org

To: the contact address on trumpstruth.org/about.

Subject: Permission to read trumpstruth.org's feed for a public market-research tracker

Hi,

I run Shitpost Alpha, an open-source project (github.com/chrisrogers37/shitpost-alpha) that tracks how markets move after Trump's Truth Social posts and grades each call in public.

We'd like your permission to read trumpstruth.org's public feed to detect new posts, no more than once every [60] seconds. We couldn't find reuse terms on the site, so we're asking rather than assuming.

How we'd use it:
- We never republish your pages or a post's full text. Public pages quote at most about 200 characters and link to the original on Truth Social.
- What we publish is our own analysis: the % move in related tickers after each post, compared with SPY.
- The service is free today. Later we may charge for tools such as filters and webhooks. If we do, we'd only rely on your feed if that commercial use is fine with you.

Would this be OK? Let us know if you'd like a credit line or a lower polling rate. If you'd rather we didn't, we'll stop.

Thanks,
[Your name]
Shitpost Alpha · [contact email]

---

## 3. Alpaca (market data): DROPPED, do not send

To: Alpaca support, using the contact form or address on alpaca.markets/support (confirm it in the browser sitting).

Subject: Publishing derived % moves from Basic (free) market data

Hi,

I'm opening a free Alpaca account for Shitpost Alpha, an open-source project that grades how stocks and crypto move after Trump's Truth Social posts.

We'd use your free market data (stocks and crypto) to compute, for each post:
- the % move of a ticker at fixed windows after the post (for example 1 hour, 1 day, 7 days);
- that move compared with SPY, or with BTC for coins;
- whether our call was a hit or a miss.

We would never show raw prices, quotes, bars or a minute-by-minute series, only those derived percentages.

Questions:
1. May we publish those derived percentages on a free public website, Telegram channel, X account and API?
2. Would the answer change if we later charged for tools such as filters, webhooks or higher API limits (not for the data itself)?
3. If we ever wanted to show actual prices, which plan or licence covers display or redistribution, and what does it cost?

A written answer would be ideal, since we keep a record of the terms behind every data source we use.

Thanks,
[Your name]
Shitpost Alpha · [contact email]
