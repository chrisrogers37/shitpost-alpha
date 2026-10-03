# Match rule v1: the reading table (engine PR 4, B1)

**Result:** the threshold is **0.85**. A past post counts as similar when its cosine score with the new post is 0.85 or more. At most 50 matches are kept, best first. The model is `bge-small-en-v1.5@5c38ec7c405e.eaa83ab2` (round 2 added a digest of the rest of the pin to the version; the vectors are bitwise the same).

The rule lives in `engine/engine/extract/match_rule.json`, and the labels in `engine/precision/match-labels.csv` (ids only). Both are on PR #261.

## How it was set

- **The posts.** The 30 posts of set `match` in `precision/samples.csv`, drawn with a fixed seed and kept apart from the 300 precision posts. They run from August 2022 to September 2026.
- **The pairs.** For each post, `python -m scripts.match_rule pairs` took its earlier posts in each score band, at most 3 per band, drawn with seed 20261002. That gave 274 pairs.
- **The reading.** Each pair was read and marked "same subject" only when both posts are about the same specific matter: the same case, person, company, election or policy. Sharing a broad topic was not enough.
- **What was looked at.** Post text only. No prices, returns or old predictions.
- **The rule for picking.** The threshold is the lowest band at which that band, and every band above it, has at least 80% same-subject pairs.

| Band | Same subject (95% Wilson interval) |
| --- | --- |
| 0.90 and up | 100% (14/14; 78% to 100%) |
| 0.85 to 0.90 | 81% (26/32; 65% to 91%) |
| 0.80 to 0.85 | 48% (28/58; 36% to 61%) |
| 0.75 to 0.80 | 21% (17/80; 14% to 31%) |
| 0.70 to 0.75 | 12% (11/90; 7% to 21%) |

## The 0.85 band is on the edge

26 of 32 is 81%. One call the other way would make it 78%, and the threshold would move up to 0.90. The calls that decided it are below; each was marked "same".

- **Ken Paxton.** His 2022 runoff against his 2023 impeachment acquittal: the same person.
- **Chris Christie.** A post on his New Jersey approval rating against a DeSantis post that compares him to Christie on that same record.
- **"Leo".** "YOU, LEO!" against "Thank you, Leo!" (2024). Both are addressed to a Leo, but it isn't certain it's the same one.
- **The MAGA slogan.** "Next November, we are going to Make America Great Again!" against the bare slogan.
- **Fox News.** Fox News coverage and ratings, counted as the same company as the Fox debate ratings.

## What fails below 0.85

- **Templated endorsements.** The endorsement posts share a template, so they score 0.80 to 0.88 against endorsements of different candidates. For example, Brandon Herrera's against Brandon Gill, Jace Yarbrough and James Gallagher. The 0.90 band held only because those pairs were the same candidate (Anna Paulina Luna, Stacy Garrity, Thomas Massie).
- **Slogans with a different point.** "MAKE AMERICA GREAT AGAIN!" against "Get out and vote" or a border post that ends in the slogan.
- **Lists of grievances.** A post on the Mar-a-Lago search that lists "Russia, impeachments, Mueller" scores 0.80 to 0.84 with other posts that carry the same list but are about the January 6th committee or the stolen-election claim.
- **The same outlet, a different story.** WaPo, NYT and Fox posts about different stories.

## The 30 posts, same/total per band

| Post | Subject | 0.90+ | 0.85 | 0.80 | 0.75 | 0.70 |
| --- | --- | --- | --- | --- | --- | --- |
| 108809454912105665 | Mar-a-Lago search as a hoax | | | 0/3 | 0/3 | 0/3 |
| 108952337524740244 | Kushner book, Nobel Prize | | | | 0/3 | 0/3 |
| 109123698568322659 | Nebraska Senate seat | | | 0/1 | 0/3 | 0/3 |
| 109542770816494369 | January 6th committee referrals | | | 2/3 | 1/3 | 1/3 |
| 109836837116461390 | Koch network | | | 0/3 | 0/3 | 0/3 |
| 110384051064378318 | Roe v. Wade | | | 1/1 | 0/3 | 0/3 |
| 110475840682787882 | DOJ and FBI election interference | | 2/2 | 3/3 | 1/3 | 1/3 |
| 110826195969815808 | Will Hurd, Fox ratings | | | | 1/3 | 0/3 |
| 110964486144064686 | DeSantis polls, Christie | 1/1 | 3/3 | 3/3 | 2/3 | 0/3 |
| 111076755850485138 | Paxton acquittal | | 2/2 | 1/3 | 1/3 | 0/3 |
| 111137924538404850 | NY civil fraud case, valuations | | 1/1 | 1/3 | 1/3 | 0/3 |
| 111146021758433442 | Fox debate ratings | 1/1 | 3/3 | 3/3 | 0/3 | 0/3 |
| 111512227817146364 | "MAKE AMERICA GREAT AGAIN!" | 3/3 | 1/3 | 1/3 | 0/3 | 0/3 |
| 111551588135419982 | NY civil fraud trial, expert | | | 1/1 | 2/3 | 1/3 |
| 111621096414641540 | Climate reparations | | | | 0/1 | 0/3 |
| 111712513152072722 | Iowa caucus turnout | | 2/2 | 3/3 | 3/3 | 2/3 |
| 111882108215156086 | Border bill | | | 1/1 | 3/3 | 3/3 |
| 112505041152285504 | Libertarian convention speech | | | | 0/3 | 0/3 |
| 113301449737228852 | Election Day turnout | 1/1 | 3/3 | 2/3 | 0/3 | 0/3 |
| 113426436990570801 | Arab and Muslim voters, Middle East | | | 2/3 | 0/3 | 0/3 |
| 115216445416479469 | "YOU, LEO!" | | 1/1 | | | 0/3 |
| 115493792769655959 | NJ governor race, Ciattarelli | 1/1 | 1/1 | 2/3 | 0/3 | 0/3 |
| 115663952570644904 | Jay Clayton | | | | | 3/3 |
| 115791817694825755 | Tariffs and the economy | | 3/3 | 2/3 | 2/3 | 0/3 |
| 115871567004197826 | Maduro order, legal view | | | | 0/1 | 0/3 |
| 115946646049401300 | Endorsing Anna Paulina Luna | 3/3 | | 0/3 | 0/3 | 0/3 |
| 116213110990414470 | Endorsing Brandon Herrera | | 0/3 | 0/3 | 0/3 | 0/3 |
| 116591756607268698 | Thomas Massie | 3/3 | 3/3 | 0/3 | 0/3 | 0/3 |
| 116596886701876953 | Endorsing Stacy Garrity | 1/1 | | | 0/3 | 0/3 |
| 117337317276437965 | Fake news in the White House | | 1/2 | 0/3 | 0/3 | 0/3 |

A blank cell means the post had no earlier posts in that band.

## What 0.85 gives over all history

These are the 16,087 embedded posts, each compared with the posts before it (`python -m scripts.match_rule coverage` prints them):

- 39.6% have at least one earlier match at 0.85.
- Among those, the median is 2 matches and the 90th percentile is 14.
- 0.9% reach the cap of 50.

## Embedding the history

- 16,087 posts embedded.
- 5,523 posts were skipped because they are only links, with no words.
- 48 were cut at 512 tokens.
- It took about 14 minutes on the sandbox's 4 CPUs, about 19 posts a second, across two runs: a container restart stopped the first, and the second resumed it.
