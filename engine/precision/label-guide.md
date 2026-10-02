# Label guide: PR 4's precision sample

Each of the 300 posts in `samples.csv` (sets `precision_window` and `precision_early`) gets
three labels, read from the post's own words, and the quoted post's words when the engine
has them, before either picker runs on it. The labels are in `labels.csv`: post id and
labels only, never the text.

## 1. Market link: yes or no

**Yes** when the post says something a trader could act on for a US-listed stock or ETF,
for bitcoin or ether, or for the market as a whole. That is, its main point, or a real part
of it, is one of:

- a government action, decision, threat or negotiation that changes conditions for
  companies, industries or markets: tariffs and trade deals, sanctions, a tax or spending
  measure, pressure on the Fed over rates, drug pricing, energy or crypto policy, rules
  for a named industry;
- a named company, product or industry in a business sense: an investment or factory, a
  deal, a lawsuit or threat against it, praise or attack aimed at the business, its stock;
- the market or the economy as such: stocks, jobs numbers, inflation and prices, rates,
  oil or gas prices, crypto prices;
- war, peace or military action involving a major economy, an oil region or a shipping
  lane, including a ceasefire or peace deal.

**No** when the economic words are campaign boilerplate (an endorsement's "Cut Taxes, Grow
the Economy, Unleash American Energy"), or the post is about elections, courts, the media,
crime, a person or himself with nothing new about the economy, a company's business or a
war. A company named in a non-business aside (she never worked at McDonald's) has no
market link, but its name is still labelled (section 3).

## 2. Topic

The subject the post is mostly about, from `engine/extract/topics.json` (its descriptions),
or `other`. The label takes the main subject, not the first match in the rules' priority
order, so labels and the rules can differ on posts with several subjects.

## 3. Names

Every US-listed stock or ETF, and bitcoin or ether, that the post names or clearly
implies, as `TICKER:e` (explicit) or `TICKER:i` (implied), separated by `;`:

- **Explicit**: named by the company's name, a product or brand of it, or its ticker,
  even in an aside. A company's former name counts (Facebook is META).
- **Implied**: not named, but the post is clearly about it: through its chief executive or
  founder acting for it ("Tim Apple" on factories, Jensen on chip exports), a description
  only it fits, or a direct, first-order industry link, where the label lists at most the
  three largest US-listed companies whose business is mostly that industry (tariffs on
  foreign steel point to NUE, STLD and CLF).
- **Not labelled**: broad index funds (SPY and QQQ come from the market link), private
  companies, companies listed only abroad or over the counter, delisted ones, news
  outlets and video platforms named as sources or targets of media posts (CNN, Fox News,
  NBC, Rumble), and Truth Social as the place he posts. A parent company named in its own
  right (Comcast, Disney, Paramount) is labelled.

"US-listed" means it trades on a US exchange today and did when the post was made.

## Groups

`precision_window`: 200 posts from 2025-11-01 (the AI picker's planned test window) to the
end of the pool. `precision_early`: 100 posts from 2022-02-01 to 2025-10-31. If B2 moves
the window start, the posts before the new start are reported as their own group.
