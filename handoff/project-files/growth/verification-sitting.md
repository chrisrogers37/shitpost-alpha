# Verification sitting: what Chris needs

Owner: thread "Plan growth and revenue". This is the hour on the verification list in the growth plan. It's due before engine PR 2, because PR 2 starts reading the post feeds.

The answers go back to the coordinator. Growth then records each one in the plan's terms register, marked "checked on" with the date.

## What to have ready
- A browser. Most pages work without logging in.
- The Telegram app, for item 5.
- Optional: an X login, for item 6.
- The two email drafts (CNN and trumpstruth) in /mnt/project-files/growth/outreach-drafts.md. The Alpaca email is dropped. Items 1 and 2 confirm where the CNN and trumpstruth emails go.

## Two ways to do it

**A. About 15 minutes of your time.** Paste the brief at the bottom into a claude.ai chat with web search turned on. Send its filled table to the coordinator. Then do item 5 yourself in the Telegram app (5 minutes) and send the emails.

**B. About an hour.** Open the links below yourself and note the answers.

Items 1 to 5 matter now. Items 6 to 8 only matter before the public launch, so they can wait if the hour runs short.

## The checks

1. **CNN's live feed.**
   - Read CNN's terms of use (https://www.cnn.com/terms) and the archive's README (https://github.com/stiles/trump-truth-social-archive).
   - Answer:
     - Do they allow automated reading of the ix.cnn.io JSON file?
     - Do they allow commercial use?
     - Who should the email go to?
   - Quote the clause that answers each.

2. **trumpstruth.org.**
   - Read https://trumpstruth.org/about, https://trumpstruth.org/faq and https://trumpstruth.org/robots.txt.
   - Answer:
     - Are any reuse terms stated?
     - Does robots.txt block the feed?
     - Who runs it, and what's the contact address for the email?

3. **Truth Social's own terms.**
   - Read https://help.truthsocial.com/legal/terms-of-service/.
   - Answer:
     - Is use personal and non-commercial only?
     - Is automated access or scraping barred?
     - Does anything cover its API?
   - Quote the clauses. The engine reads this API live, so the answer decides whether a paid tier could ever rely on it.

4. **ScrapeCreators.**
   - Read its terms (linked from https://scrapecreators.com).
   - Answer: may data returned by its Truth Social endpoint be used in a commercial product?

5. **Telegram** (in the app).
   - Answer:
     - Does a channel's invite link show how many people joined through it (Manage channel > Invite links)?
     - Can a public username be removed from one channel and set on another in the same sitting?
   - From https://core.telegram.org/bots/faq (the section on limits): how many messages per second can a bot send?

6. **X** (can wait until before the launch).
   - Read the current API pricing at https://docs.x.com and the automation rules at https://help.x.com/en/rules-and-policies/x-automation.
   - Answer:
     - What does one post cost through the API?
     - Does a post with a link cost more?
     - How is the Automated label turned on?

7. **Rivals** (can wait until before the launch).
   - Check Trump Market Tracker, Trump Tracker and the TACO Index.
   - Answer: does any of them publish a graded record of its calls against a benchmark such as SPY?

8. **Reddit and Hacker News** (can wait until before the launch).
   - Read the rules on posting your own project for r/dataisbeautiful, r/investing, r/stocks and r/wallstreetbets, and the Show HN guidelines (https://news.ycombinator.com/showhn.html).
   - Answer: which of them allow a data post about our own report?

## Brief to paste into a claude.ai chat with web search

> I need a factual check of public terms pages, with quotes. Don't give legal advice; quote what the pages say and give the link and today's date for each. If a page won't load or says nothing on a point, say "not stated".
>
> Answer each question below in a table with these columns: item, question, answer (yes / no / not stated), exact quote, link.
>
> 1. CNN's terms of use (cnn.com/terms) and the README of github.com/stiles/trump-truth-social-archive: may an automated program read the JSON file at ix.cnn.io that this archive is built from? Is commercial use of the data allowed? Who should a permission request go to?
> 2. trumpstruth.org (its about page, FAQ and robots.txt): are any reuse terms stated? Does robots.txt disallow automated access to its feed? Who runs the site, and what is its contact address?
> 3. Truth Social's terms of service (help.truthsocial.com/legal/terms-of-service/): is use limited to personal, non-commercial use? Is automated access or scraping prohibited? Is there anything about API access?
> 4. ScrapeCreators' terms (scrapecreators.com): may data returned by its API be used in a commercial product?
> 5. Telegram's bot FAQ (core.telegram.org/bots/faq): what are the bot's sending limits per second, and per minute to one group?
> 6. X's current API pricing (docs.x.com): what does one post cost, and does a post containing a link cost more? From X's automation rules (help.x.com), how is the "Automated" account label turned on?
> 7. Do "Trump Market Tracker", "Trump Tracker" or the "TACO Index" publish a graded track record of their calls against a benchmark such as SPY? Link what you find.
> 8. What do the rules of r/dataisbeautiful, r/investing, r/stocks and r/wallstreetbets, and Hacker News's Show HN guidelines, say about posting your own project or data analysis?
