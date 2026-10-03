# Backtest v1: the Gate 0 report

Judged against [Gate 0, version 1](gate0-v1.md) as written (SHA-256 `b16fe89da2fde01da0af858804abe52c46f45229d89e549bed787c1043d4667a`). Moves are % moves in the called direction, net of beta times the market for a company and for ETH; costs are round trips. Every number counts New York days, not calls.

## Result

**Gate 0 passes:** 1 of 22 pairs pass (rules SPY at 1 hour). A pass is a backtest result, before any live sample: the paid gate still needs the live days below.

Text posts from 2022-02-01 to 2022-03-31: 86. The rules picker answered 86 of them; the AI picker answered 0 (from 2025-11-01).

## The 22 gate tests

Conditions: 1, at least 30 days with calls; 2, entry 2 minutes after the post; 3, the mean after 20 bp is above zero; 4, q under 0.10 (Benjamini-Hochberg across the 22 tests); 5, the mean over the last 12 months is above zero from at least 10 days.

| Picker | Pair | Calls | Days | Mean after 20 bp | After 5 bp | Hit rate (95% interval) | p | Last 12 months | q | 1 | 2 | 3 | 4 | 5 | Passes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | SPY at 1 hour | 31 | 31 | +80.8 bp | +95.8 bp | 100.0% (89.0% to 100.0%) | 0.0001 | +80.8 bp over 31 days | 0.0022 | yes | yes | yes | yes | yes | **yes** |
| rules | SPY at the close | 19 | 19 | +214.3 bp | +229.3 bp | 89.5% (68.6% to 97.1%) | 0.8057 | +214.3 bp over 19 days | 1.0000 | no | yes | yes | no | yes | no |
| rules | SPY at 1 trading day | 22 | 22 | +214.9 bp | +229.9 bp | 95.5% (78.2% to 99.2%) | 0.8268 | +214.9 bp over 22 days | 1.0000 | no | yes | yes | no | yes | no |
| rules | QQQ at 1 hour | 2 | 2 | -22.3 bp | -7.3 bp | 50.0% (9.5% to 90.5%) | 0.1594 | -22.3 bp over 2 days | 1.0000 | no | yes | no | no | no | no |
| rules | QQQ at the close | 4 | 4 | +1293.0 bp | +1308.0 bp | 100.0% (51.0% to 100.0%) | 0.6482 | +1293.0 bp over 4 days | 1.0000 | no | yes | yes | no | no | no |
| rules | QQQ at 1 trading day | 4 | 4 | +1367.6 bp | +1382.6 bp | 100.0% (51.0% to 100.0%) | 0.2547 | +1367.6 bp over 4 days | 1.0000 | no | yes | yes | no | no | no |
| rules | BTC at 1 hour | 2 | 2 | -42.4 bp | -27.4 bp | 0.0% (0.0% to 65.8%) | 0.9084 | -42.4 bp over 2 days | 1.0000 | no | yes | no | no | no | no |
| rules | BTC at 4 hours | 2 | 2 | -54.7 bp | -39.7 bp | 0.0% (0.0% to 65.8%) | 0.8447 | -54.7 bp over 2 days | 1.0000 | no | yes | no | no | no | no |
| rules | BTC at 24 hours | 18 | 18 | -19.8 bp | -4.8 bp | 50.0% (29.0% to 71.0%) | 0.4042 | -19.8 bp over 18 days | 1.0000 | no | yes | no | no | no | no |
| rules | The company at the close | 11 | 11 | +2111.5 bp | +2126.5 bp | 100.0% (74.1% to 100.0%) | 0.2023 | +2111.5 bp over 11 days | 1.0000 | no | yes | yes | no | yes | no |
| rules | The company at 1 trading day | 10 | 10 | +2063.6 bp | +2078.6 bp | 100.0% (72.2% to 100.0%) | 0.3614 | +2063.6 bp over 10 days | 1.0000 | no | yes | yes | no | yes | no |
| AI vote | SPY at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | SPY at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | SPY at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | QQQ at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | QQQ at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | QQQ at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | BTC at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | BTC at 4 hours | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | BTC at 24 hours | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | The company at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| AI vote | The company at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |

## Which picker picks

The AI picker has no answers in the sample, so there is no head-to-head: **the rules pick.**
The winner's figure is flattering: it is the better of two.

## Posts a year the send rule would have sent

31 posts with a surviving call on a passing pair of the picking picker (rules): 191.9 a year.

## The live sample the paid gate needs

Days of calls that confirm each passing pair's hit rate against 50% (one-sided, 5% error, 80% power):

- rules SPY at 1 hour: hit rate 100.0%, 3 days

## Also reported, never judged

p-values here are not adjusted, and none of these can pass the gate.

Without answers in the sample, so left out below: AI vote, GPT-4.1 alone, Haiku 4.5 alone.

### The rules on the posts both pickers were tested on (with the filters)

| Picker | Pair | Calls | Days | Mean after 20 bp | After 5 bp | Hit rate (95% interval) | p | Last 12 months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | SPY at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | SPY at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | SPY at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | QQQ at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | QQQ at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | QQQ at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | BTC at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | BTC at 4 hours | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | BTC at 24 hours | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | The company at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | The company at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |

### Mirrors-only delay: alert at the post plus 20 minutes (not judged now)

| Picker | Pair | Calls | Days | Mean after 20 bp | After 5 bp | Hit rate (95% interval) | p | Last 12 months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | SPY at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | SPY at the close | 8 | 8 | +32.0 bp | +47.0 bp | 62.5% (30.6% to 86.3%) | 0.9884 | +32.0 bp over 8 days |
| rules | SPY at 1 trading day | 9 | 9 | +55.4 bp | +70.4 bp | 88.9% (56.5% to 98.0%) | 0.9745 | +55.4 bp over 9 days |
| rules | QQQ at 1 hour | 2 | 2 | -65.8 bp | -50.8 bp | 0.0% (0.0% to 65.8%) | 0.8137 | -65.8 bp over 2 days |
| rules | QQQ at the close | 4 | 4 | +1293.0 bp | +1308.0 bp | 100.0% (51.0% to 100.0%) | 0.6568 | +1293.0 bp over 4 days |
| rules | QQQ at 1 trading day | 5 | 5 | +1333.3 bp | +1348.3 bp | 100.0% (56.6% to 100.0%) | 0.3731 | +1333.3 bp over 5 days |
| rules | BTC at 1 hour | 2 | 2 | -33.0 bp | -18.0 bp | 50.0% (9.5% to 90.5%) | 0.5209 | -33.0 bp over 2 days |
| rules | BTC at 4 hours | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | BTC at 24 hours | 12 | 12 | -34.8 bp | -19.8 bp | 33.3% (13.8% to 60.9%) | 0.4886 | -34.8 bp over 12 days |
| rules | The company at the close | 12 | 12 | +2184.2 bp | +2199.2 bp | 100.0% (75.8% to 100.0%) | 0.0672 | +2184.2 bp over 12 days |
| rules | The company at 1 trading day | 11 | 11 | +2093.1 bp | +2108.1 bp | 100.0% (74.1% to 100.0%) | 0.2762 | +2093.1 bp over 11 days |

### Every market-link post with a call, without rules 3, 4 and 6

| Picker | Pair | Calls | Days | Mean after 20 bp | After 5 bp | Hit rate (95% interval) | p | Last 12 months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | SPY at 1 hour | 42 | 42 | +78.9 bp | +93.9 bp | 100.0% (91.6% to 100.0%) | 0.0001 | +78.9 bp over 42 days |
| rules | SPY at the close | 42 | 42 | +299.4 bp | +314.4 bp | 90.5% (77.9% to 96.2%) | 0.2309 | +299.4 bp over 42 days |
| rules | SPY at 1 trading day | 40 | 40 | +285.6 bp | +300.6 bp | 92.5% (80.1% to 97.4%) | 0.3644 | +285.6 bp over 40 days |
| rules | QQQ at 1 hour | 35 | 35 | -28.4 bp | -13.4 bp | 42.9% (28.0% to 59.1%) | 0.7407 | -28.4 bp over 35 days |
| rules | QQQ at the close | 42 | 42 | +1354.9 bp | +1369.9 bp | 100.0% (91.6% to 100.0%) | 0.4330 | +1354.9 bp over 42 days |
| rules | QQQ at 1 trading day | 40 | 40 | +1359.4 bp | +1374.4 bp | 100.0% (91.2% to 100.0%) | 0.3205 | +1359.4 bp over 40 days |
| rules | BTC at 1 hour | 32 | 32 | -29.3 bp | -14.3 bp | 34.4% (20.4% to 51.7%) | 0.8560 | -29.3 bp over 32 days |
| rules | BTC at 4 hours | 34 | 34 | -29.9 bp | -15.0 bp | 41.2% (26.4% to 57.8%) | 0.6129 | -29.9 bp over 34 days |
| rules | BTC at 24 hours | 40 | 40 | -10.2 bp | +4.8 bp | 55.0% (39.8% to 69.3%) | 0.5584 | -10.2 bp over 40 days |
| rules | The company at the close | 42 | 42 | +2059.8 bp | +2074.8 bp | 100.0% (91.6% to 100.0%) | 0.3444 | +2059.8 bp over 42 days |
| rules | The company at 1 trading day | 40 | 40 | +2098.1 bp | +2113.1 bp | 100.0% (91.2% to 100.0%) | 0.2194 | +2098.1 bp over 40 days |

### Pre-market entry, SPY and QQQ

| Picker | Pair | Calls | Days | Mean after 20 bp | After 5 bp | Hit rate (95% interval) | p | Last 12 months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | SPY at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | SPY at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | SPY at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | QQQ at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | QQQ at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | QQQ at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |

### ETH, the 5- and 15-minute windows, and XLE for the energy topic

| Picker | Pair | Calls | Days | Mean after 20 bp | After 5 bp | Hit rate (95% interval) | p | Last 12 months |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | ETH at 1 hour | 2 | 2 | +28.1 bp | +43.1 bp | 100.0% (34.2% to 100.0%) | 0.0274 | +28.1 bp over 2 days |
| rules | ETH at 4 hours | 2 | 2 | -73.6 bp | -58.5 bp | 0.0% (0.0% to 65.8%) | 0.8518 | -73.6 bp over 2 days |
| rules | ETH at 24 hours | 7 | 7 | -53.3 bp | -38.3 bp | 28.6% (8.2% to 64.1%) | 0.6203 | -53.3 bp over 7 days |
| rules | SPY at 5 minutes | 33 | 33 | +71.9 bp | +86.9 bp | 100.0% (89.6% to 100.0%) | 0.0001 | +71.9 bp over 33 days |
| rules | SPY at 15 minutes | 33 | 33 | +70.8 bp | +85.8 bp | 97.0% (84.7% to 99.5%) | 0.0001 | +70.8 bp over 33 days |
| rules | QQQ at 5 minutes | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | QQQ at 15 minutes | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | BTC at 5 minutes | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | BTC at 15 minutes | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | The company at 5 minutes | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | The company at 15 minutes | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | XLE at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | XLE at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | XLE at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |

## What the filters dropped and what was skipped

| Picker | Pair | burst | few match days | no matches | no random moves | not better than random | not one way | not yet | tie |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | SPY at 1 hour | 0 | 9 | 1 | 0 | 2 | 0 | 0 | 0 |
| rules | SPY at the close | 0 | 9 | 1 | 0 | 14 | 0 | 0 | 0 |
| rules | SPY at 1 trading day | 0 | 9 | 2 | 0 | 9 | 0 | 1 | 0 |
| rules | QQQ at 1 hour | 0 | 7 | 1 | 0 | 6 | 20 | 0 | 7 |
| rules | QQQ at the close | 0 | 9 | 1 | 0 | 29 | 0 | 0 | 0 |
| rules | QQQ at 1 trading day | 0 | 9 | 2 | 0 | 28 | 0 | 0 | 0 |
| rules | BTC at 1 hour | 0 | 8 | 1 | 0 | 0 | 22 | 0 | 10 |
| rules | BTC at 4 hours | 0 | 7 | 1 | 0 | 0 | 25 | 0 | 8 |
| rules | BTC at 24 hours | 0 | 8 | 1 | 0 | 4 | 11 | 0 | 1 |
| rules | The company at the close | 0 | 9 | 1 | 0 | 22 | 0 | 0 | 0 |
| rules | The company at 1 trading day | 0 | 9 | 2 | 0 | 22 | 0 | 0 | 0 |
| AI vote | SPY at 1 hour | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | SPY at the close | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | SPY at 1 trading day | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | QQQ at 1 hour | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | QQQ at the close | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | QQQ at 1 trading day | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | BTC at 1 hour | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | BTC at 4 hours | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | BTC at 24 hours | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | The company at the close | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| AI vote | The company at 1 trading day | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## Bursts

Across all 86 text posts (PR 2's measure), the gap to the previous post is 0.0% within 5 minutes, 0.0% within 15 minutes, 0.0% within 30 minutes, 0.0% within 60 minutes; the sample's 86 posts fall in 86 clusters. Rule 6 (one call per instrument per 30 minutes) dropped 0 calls across the 22 gate tests.

## The match rule, as read and as served

Match rule v1's threshold was set by reading up to 3 earlier posts per score band for each read post. The rule serves up to 50 matches a post, so a post with many neighbours counts for more in what is served than in what was read. The last column counts each read post's share once for every match the rule serves it in that band (0 of the read posts are in the sample).

| Score | Pairs read | Same subject, as read (95% interval) | Matches served | Same subject, weighted by matches served |
| --- | --- | --- | --- | --- |
| 0.90 and up | 14 | 100% (14/14; 78% to 100%) | 0 | n/a |
| 0.85 to 0.90 | 32 | 81% (26/32; 65% to 91%) | 0 | n/a |
| 0.85 and up | 46 | 87% (40/46; 74% to 94%) | 0 | n/a |

## Inputs

- Gate 0 v1: `b16fe89da2fde01da0af858804abe52c46f45229d89e549bed787c1043d4667a`
- Rules version 1: `a5abd56a85d8f57cb2e39ddd4546b09f302522b4d5116992e25e77ea5f10b809`
- AI picker version 1: `750126437c71c40cf07dcd9f870fb2742b9a81c4e173c2ff9989344ecce250b1`
- Match rule version 1: `4a06e9dce150b2cc570de7872fd59deef8ee6f3def7ef5199b3a61f30f1e9d81` (score 0.85 or more, at most 50)
- Similarity model: bge-small-en-v1.5@5c38ec7c405e.eaa83ab2
