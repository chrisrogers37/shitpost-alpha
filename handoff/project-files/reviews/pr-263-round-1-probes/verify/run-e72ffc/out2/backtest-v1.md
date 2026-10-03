# Backtest v1: the Gate 0 report

Judged against [Gate 0, version 1](gate0-v1.md) as written (SHA-256 `b16fe89da2fde01da0af858804abe52c46f45229d89e549bed787c1043d4667a`). Moves are % moves in the called direction, net of beta times the market for a company and for ETH; costs are round trips. Every number counts New York days, not calls.

## Result

**Gate 0 does not pass:** none of the 22 pairs passes all five conditions. No edge was found under Gate 0's rules.

Text posts from 2022-02-01 to 2022-03-31: 86. The rules picker answered 86 of them; the AI picker answered 0 (from 2025-11-01).

## The 22 gate tests

Conditions: 1, at least 30 days with calls; 2, entry 2 minutes after the post; 3, the mean after 20 bp is above zero; 4, q under 0.10 (Benjamini-Hochberg across the 22 tests); 5, the mean over the last 12 months is above zero from at least 10 days.

| Picker | Pair | Calls | Days | Mean after 20 bp | After 5 bp | Hit rate (95% interval) | p | Last 12 months | q | 1 | 2 | 3 | 4 | 5 | Passes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rules | SPY at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | SPY at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | SPY at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | QQQ at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | QQQ at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | QQQ at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | BTC at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | BTC at 4 hours | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | BTC at 24 hours | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | The company at the close | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
| rules | The company at 1 trading day | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days | 1.0000 | no | yes | no | no | no | no |
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

## Posts a year the send rule would have sent

0 posts with a surviving call on a passing pair of the picking picker (rules): 0.0 a year.

## The live sample the paid gate needs

None: no pair passed.

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

### Every market-link post with a call, without rules 3, 4 and 6

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
| rules | ETH at 1 hour | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | ETH at 4 hours | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | ETH at 24 hours | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | SPY at 5 minutes | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
| rules | SPY at 15 minutes | 0 | 0 | n/a | n/a | n/a | 1.0000 | no days |
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

| Picker | Pair | burst | no matches | no random moves |
| --- | --- | --- | --- | --- |
| rules | SPY at 1 hour | 0 | 43 | 0 |
| rules | SPY at the close | 0 | 43 | 0 |
| rules | SPY at 1 trading day | 0 | 43 | 0 |
| rules | QQQ at 1 hour | 0 | 43 | 0 |
| rules | QQQ at the close | 0 | 43 | 0 |
| rules | QQQ at 1 trading day | 0 | 43 | 0 |
| rules | BTC at 1 hour | 0 | 43 | 0 |
| rules | BTC at 4 hours | 0 | 43 | 0 |
| rules | BTC at 24 hours | 0 | 43 | 0 |
| rules | The company at the close | 0 | 43 | 0 |
| rules | The company at 1 trading day | 0 | 43 | 0 |
| AI vote | SPY at 1 hour | 0 | 0 | 0 |
| AI vote | SPY at the close | 0 | 0 | 0 |
| AI vote | SPY at 1 trading day | 0 | 0 | 0 |
| AI vote | QQQ at 1 hour | 0 | 0 | 0 |
| AI vote | QQQ at the close | 0 | 0 | 0 |
| AI vote | QQQ at 1 trading day | 0 | 0 | 0 |
| AI vote | BTC at 1 hour | 0 | 0 | 0 |
| AI vote | BTC at 4 hours | 0 | 0 | 0 |
| AI vote | BTC at 24 hours | 0 | 0 | 0 |
| AI vote | The company at the close | 0 | 0 | 0 |
| AI vote | The company at 1 trading day | 0 | 0 | 0 |

## Bursts

Across all 87 text posts (PR 2's measure), the gap to the previous post is 0.0% within 5 minutes, 0.0% within 15 minutes, 1.2% within 30 minutes, 1.2% within 60 minutes; the sample's 86 posts fall in 86 clusters. Rule 6 (one call per instrument per 30 minutes) dropped 0 calls across the 22 gate tests.

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
