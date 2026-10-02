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
- `scrapecreators_posts.unverified.json`: ScrapeCreators' `{"success": true, "posts": [...]}`.
- `challenge.unverified.html`: a Cloudflare challenge page.
