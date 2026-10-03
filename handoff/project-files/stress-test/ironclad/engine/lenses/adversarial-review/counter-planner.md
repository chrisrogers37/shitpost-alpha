# Counter-Planner: evidence first, specific now

Inline pass 5 of 6, run in sequence, having read passes 1–4. This is a real alternative, not a straw man.

## The opposite assumptions
| The plan assumes | The counter-plan assumes |
|---|---|
| Build the live system and its general data model first, and check the edge at PR 10 | The edge is the only unknown that matters, so answer it first for $0 |
| One general schema (sources, feeds, venues, price rights, slugs) so later sources are a row | One source, one vendor, one asset class until the evidence asks for more; generalize at PR 12 |
| The LLM decides direction, so the evidence splits into 3 layers | A deterministic labeller decides topic and instrument, statistics decide direction, the LLM writes the reason |
| Live prices and per-minute progress are core | Results at the window ends are core; live progress is a paid-tier feature after an edge |

## The counter-plan
- **E0 (sandbox, about 1 week, $0).** Import the CNN archive to sandbox Postgres. Get Alpaca bars per post window for SPY, QQQ, sector ETFs, BTC and ETH, plus every ticker a keyword rule names. Topic list v1 and alias rules. Run the event study against the benchmark and a placebo for a pre-registered primary family. Report to Chris. **Gate.**
- **L1 (only what replacing the old system needs).** Engine foundation and CI; the two pollers, `signals` and sightings; deterministic labelling plus the LLM reason line; `alerts` and insert-only `alert_revisions` with the cursor; N1 Telegram; shadow week; cutover. About 10 tables. This is built whatever E0 says, because it meets goals 1–2 and stops the broken old pipeline and the ScrapeCreators bill.
- **G1 (only if E0 shows an edge, and only for its windows).** Evidence lines and tiers, outcome revisions, the dashboard evidence pages. Live streams and progress only if the edge is in minutes. Crypto alerting only if BTC/ETH show an edge. Slugs and ticker pages for the instruments that have one.
- **If there is no edge:** L1 still ships as an honest 'post alert' feed with graded results, and the rest is rethought before more is spent.

## What it gets right that the plan doesn't
- The deciding answer arrives in about a week, before any growth surface is built.
- Alert evidence and alerts share one labeller and one full-history population, with no memorization problem.
- About half the tables and one of the two lanes of live machinery go away until they are needed.

## What it gives up
- The LLM's own calls get no measured record until the live record builds up. Option (c) accepts that.
- The keyword labeller misses posts the LLM would catch, a recall loss on alert coverage.
- The public channel's start may slip if Chris wants evidence before going public.
- A second schema migration is needed when sources and venues are added later. That is cheap with Alembic.

## Synthesis (what result.md recommends)
Keep the plan's PR order 1–5. Add the gate after PR 5. Cut PR 6 down to L1's alert core. Move streams, progress, crypto alerting, slug redirects, price rights and the old-record import behind the gate. Adopt the deterministic evidence key.
