# Site PR D1: go-live site

You are building D1, the second of three website PRs in chrisrogers37/shitpost-alpha. D1 is the minimum public website for Shitpost Alpha, a service that calls Trump's market-moving posts within minutes and grades every call in public:
- a home page and a page for every call;
- /about;
- the rule that lets search engines list the site.

D1 merges during the engine's shadow week. shitpostalpha.com points at it from the shadow week too, so DNS and the certificate settle early, but the domain shows only a holding page until go-live; the full site is checked on the Railway address that week. Results, the record, ticker views, the report and the follow buttons come in D2 at the public launch.

The rest of the repo is the old system, shut down in production. Don't import it or copy its design. Design from first principles.

## What exists (read these first and build on them)
- **D0** (site): the web process `python -m engine web` in `engine/engine/web/`, with the `/api/v1` conventions written up under "Public API" in `engine/README.md`:
  - explicit Pydantic models, `stream_id` on every body, `items`/`next_before` paging, the JSON error shape, a short response cache, CORS and security headers;
  - the real-visitor rate limiter, `/healthz` and `engine/engine/links.py` (`signal_url`);
  - the no-price schema test, and tests that run as the real web role.
- **Engine PRs 1 to 6:** signals with a short `public_id`, and alerts holding alert.v1. Alert.v1 carries the instruments, calls, disposition `sent` or `fyi` with an FYI reason, `published_at`, `alerted_at`, an `excerpt` (200 characters or less, links removed) and the `analogs` block (similar past posts and how they moved, % only). PR 6 also adds the insert-only `alert_revisions` with their `seq`, and the engine status with the time it last checked for posts.
- **N1** (notifications): the `app.public_posts` view, granted to the web role. It holds only live sends of alerts and result replies to the real Telegram channel and X: alert id, revision, place and url. Its first row is the first alert the channel gets after the cutover.
- **N2** (notifications):
  - routes `GET /api/v1/alerts?before=&limit=`, `/api/v1/alerts/changes?after=` (with `head_seq`, `has_more` and a 5 s cache) and `/api/v1/alerts/{public_id}`;
  - the switch that keeps results out of public responses until the launch.

Reuse N2's query and serializer functions; never write a second query for the same data. If what you need isn't there, ask before working around it.

Send site questions to the site planner (session_01KCJr6bPZiRiCHvXaSz29dj), engine data questions to the engine planner (session_01Gw4reivJGz4EWbyB29SbDJ) and API questions to the notification planner (session_01AtzsNEeSfgd3ue1kHfPDk8), each with send_message. If an answer isn't needed to keep going, pick a sensible default, note it in the PR and carry on.

## Rules (non-negotiable)
- **Merging.** Never merge, approve or enable auto-merge. Open a draft PR and stop; Chris merges. Ignore the admin-merge pre-approval in the repo's CLAUDE.md.
- **Databases.** Never touch a production database. Never read or set DATABASE_URL. Locally, use the sandbox Postgres in DEV_DATABASE_URL.
- **Keys.** Never set OPENAI_API_KEY, ANTHROPIC_API_KEY or XAI_API_KEY. D1 needs no keys.
- **Outside services.** No Telegram, email or SMS, no crons, no Railway calls.
- **No prices.** No page or response shows a price, a bar, an entry price, a minute chart or anything from the `prices` schema, which the web role can't read. Numbers are % moves, moves against the benchmark, counts and times.
- **No results before the launch.** While N2's switch is off, no page shows a grade, hit or miss, or a result revision.
- **Text is text.** Post text and alert text always render as escaped text, in the page body and in meta tags. Never mark them safe.
- **Scope.** Build nothing listed under "Not in D1". Test-only code stays thin and is marked test-only.

## Environment
- Python 3.13 venv at /home/user/venv; if `python --version` isn't 3.13, use /home/user/venv/bin/python. Install the engine with `pip install -e "engine[dev]"`.
- Postgres 16 in DEV_DATABASE_URL, with throwaway test databases (run `service postgresql start` if it has stopped).
- Chromium is preinstalled for Playwright (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`). Never run `playwright install` in the sandbox.

## Scope

**1. How pages are built.**
- **Templates:** server-rendered with Jinja2 templates in `engine/engine/web/`, with autoescape on.
- **Static files:** one stylesheet and one small plain-JavaScript file (well under 100 lines), served by the app with long cache headers and a content hash in the URL. No Node build, no CDN and no web fonts (system font stack).
- **Look:**
  - plain and dense, light only;
  - built phone-first, with no sideways scroll at 360 px;
  - times in Eastern time with an "ET" label;
  - every move signed with an arrow as well as a colour.
- **Logo:** the eagle stays. Take it from history with `git show 139b145:frontend/public/eagle.svg`; D0 deleted the old frontend.
- **Error pages:** HTML pages for 404, 429, 500 and 503 outside `/api/`.
- **Footer on every page:** "Not investment advice."

**2. Home `/`.**
- **The promise.** "Trump's posts that move markets, called within N minutes". N is the median of `alerted_at − published_at` over sent alerts in the last 30 days, rounded up to a whole minute. Below 10 alerts it reads "called within minutes".
- **The latest calls,** newest first, read through N2's list. Each row shows:
  - the time;
  - each ticker with its direction;
  - the similar-posts line (`analogs.text`);
  - "Sent" or "FYI, not sent".

  Twenty at a time, with an "Older" link (`?before=`). Calls from before the cutover (the shadow week) must not appear publicly once the cutover has happened. Confirm with the engine planner how that is marked and that N2's list already drops them; if it doesn't, ask instead of filtering on the page.
- **New calls appear by themselves.** The script polls `/api/v1/alerts/changes?after=<head_seq rendered into the page>` every 30 s while the tab is visible.
  - On a new entry, it fetches the server-rendered list fragment and swaps it in. That is a small HTML route, cached 5 s; no templating in JavaScript.
  - On a 429 or an error, it doubles the wait (up to 5 minutes) and never retries at once.
  - If `stream_id` differs from the page's, it reloads the page.
- **Freshness dot** in the header. It turns grey with "Last check 12 min ago" when the engine hasn't checked for posts in 10 minutes. It names no feed.
- **Following.** Until the launch the Telegram channel is invite-only, so there is no join button. The follow area says "Following opens at the public launch."

**3. Call page `/s/<public_id>`.**
- **The call as first sent:** the alert's first revision word for word, with its time, and "Sent" or "FYI, not sent" with the FYI reason in plain words. Later non-result revisions are listed below it, each with its time.
- **"Sent here" links,** one per row in `app.public_posts` for this alert (channel and X). Before the launch, label them as opening only for channel members.
- **The post:**
  - alert.v1's `excerpt`, with a link to the original. Growth's rule caps excerpts at about 200 characters; it overrides the plan's 280;
  - when it was posted;
  - "called N min after the post".
- **Similar past posts.** For each instrument and window in `analogs`: how many there were, the share that moved the same way, the median move, the move against the benchmark, and the median at random times. Under 20 cases, hide the rate and say "14 cases, too few for a rate". Show up to three examples, each linking to its own `/s/` page and labelled backtest or live. Take windows and benchmarks from the data, never hard-coded.
- **How it did.** Until the launch, this section says only "Results for every call since the cutover go public at the launch." D2 fills it in.
- **A past post that was never alerted.** One that appears as a similar-post example gets a short page:
  - an excerpt of its text (200 characters or less, links removed, same rule);
  - the link to the original;
  - what followed at each window, if the engine stores those moves (ask the engine planner where; leave the section out if they don't exist yet);
  - "Never alerted".

  Any other id gets a 404.
- **Link previews** on every page:
  - title, description and canonical link, built with `signal_url` or `SITE_URL`;
  - `og:title`, `og:description`, `og:url` and `og:image`, and `twitter:card` set to `summary_large_image`.

  The image is one fixed 1200×630 PNG per page type, made once (for example a screenshot of an HTML card with the preinstalled Chromium) and committed, each under 100 KB. Nothing is drawn at request time.
- **JSON twin.** `GET /api/v1/signals/<public_id>` returns the page's data under D0's conventions:
  - `kind` (`alert` or `past_post`);
  - the alert part, from N2's serializer;
  - the excerpt, the original link and `called_after_minutes`;
  - the sent-here links.

  Every number on the page comes from this response.

**4. `/about`.** It covers:
- how posts are read and scored;
- how similar posts are found;
- the windows and benchmarks;
- how calls are graded;
- what FYI means;
- "Not investment advice.";
- "The operator may hold positions in what the service calls and trades only after an alert is public.";
- the correction policy: a call is never edited; a correction is a new, dated version shown on the call's page;
- "No comments, by design.";
- for agents: the API schema at `/api/v1/openapi.json`.

If engine PR 8 has named the public repo that receives each day's hash of new calls, link it as the way to check that no call was changed.

**5. Search listing (Chris chose "List early").**
- **Before:** until `app.public_posts` has its first row, the whole site asks not to be listed:
  - `robots.txt` disallows everything;
  - every page carries `<meta name="robots" content="noindex">` and `X-Robots-Tag: noindex`.
- **After:** from the first row (read through a cached check, about 60 s):
  - `robots.txt` allows everything except `/api/` and names the sitemap;
  - pages may be listed.
- **Always unlisted:**
  - the never-alerted past-post pages;
  - every page served on any host other than shitpostalpha.com (the Railway address).

  Pages serve on any host and never redirect, and canonical links always name https://shitpostalpha.com.
- **Sitemap:** `/sitemap.xml`, only while listed. It holds `/`, `/about` and every alerted `/s/` page with its last change; past posts that were never alerted stay out.

**6. Holding page until go-live.** A web setting `WEB_HOLDING_PAGE`, on unless set to `off`, keeps shitpostalpha.com closed through the shadow week so nobody sees shadow-week alerts there. While it is on, a request whose host is shitpostalpha.com gets:
- the holding page for any page path: the name, the eagle and one line, "Trump's market-moving posts, called within minutes. Opening soon.", with noindex;
- the JSON `unavailable` error (503) for any `/api/` path;
- `Disallow: /` from `robots.txt`.

`/healthz` and static files stay live on every host, and every other host (the Railway address) serves the full site. Chris sets `WEB_HOLDING_PAGE=off` at go-live; from then the listing rule in step 5 applies on the domain as written.

**7. Rate limits.** D0's limiter covers pages and the list fragment. Static files and `/healthz` are exempt.

**8. README.** Finish "Web service" in `engine/README.md` with the settings Chris enters in Railway:
- root directory `engine/` and no config file;
- start command `python -m engine web`;
- health check `/healthz`;
- no pre-deploy command;
- variable `WEB_DATABASE_URL` (the web role's connection string);
- the custom domain shitpostalpha.com, added before the shadow week;
- `WEB_HOLDING_PAGE`, left unset (holding page on) until go-live, then `off`.

## Not in D1
D2 builds these:
- results;
- the record and ticker views;
- the report;
- the sponsor line;
- the follow buttons.

These wait in the plan's Later list:
- a status page;
- dark mode;
- a written reason line;
- prices or a minute chart;
- analytics and `?ref` tags;
- generated preview images.

## How to check your work
From `engine/`, ruff, ruff format --check, mypy and pytest all pass, and CI is green. Add Playwright to the dev dependencies and a Chromium install step to `.github/workflows/engine.yml`. Build fixtures through the engine's and N1's own writers, not raw inserts, so they stay valid. The tests show:
- **Previews:** every page fetched without JavaScript has its title, description, canonical link and preview tags.
- **JSON twins:** each page's numbers equal its JSON twin.
- **States:** every state renders on an empty database: no calls yet, fewer than 20 cases, engine late, before the launch.
- **Hostile text:** post text with `<script>`, a broken-out attribute, a right-to-left override and a 300-character word renders as text, in the body and the meta tags.
- **Browser:** one Playwright test at 360×780 on home and a call page finds no sideways scroll, and sees the list refresh after a new alert is written (with a shortened poll interval).
- **Holding page:** with the setting unset, every page on the shitpostalpha.com host is the holding page and every `/api/` path is a 503, while `/healthz` answers and the Railway host serves the full site. With `off`, the domain serves the full site.
- **Listing:** before the first `public_posts` row, robots disallows and every page says noindex. After it, robots allows and the sitemap lists alerted pages only. Never-alerted pages and the Railway host stay noindex.
- **Rules still hold:**
  - the no-price test passes with every new route;
  - no grade appears while N2's switch is off;
  - the app runs as the web role.

Run `python -m engine web` against a test database holding fixture alerts and look at each page at phone width.

Before pushing, re-read your diff as a reviewer hunting for reasons to reject it.

## Deliver
1. **Branch** from the branch that carries D0, engine PR 6, N1 and N2 (normally N2's, which stacks on the others) while they are unmerged, or from main once they have merged. Commit and push.
2. **Draft PR** against main titled "Site D1: go-live site". Near the top, say that it goes in after D0, engine PR 6, N1 and N2, and is merged during the shadow week. The body has:
   - a "Before:" paragraph and an "After:" paragraph;
   - a short "How";
   - how you tested it;
   - phone-width screenshots of home and a call page;
   - anything not done.
3. **Changelog.** Add a CHANGELOG.md entry under [Unreleased].
4. **Stop.** No merge and no further PRs. Report the PR link and anything unfinished.
