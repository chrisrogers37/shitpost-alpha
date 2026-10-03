# Mirror lag poll from the planning thread (2026-09-30, 15:19 to 17:13 UTC)

Sandbox measurement for the latency section of the signal engine plan. Mirrors only; truthsocial.com was never called.
`lagpoll.py` polls the CNN archive every 20 s (ETag, then a 32 KB Range read) and trumpstruth's RSS every 30 s,
both the Cloudflare-cached `/feed` and an uncached `/feed?t=<n>`. Lag = first seen minus the post time decoded from the status ID.

| Post (UTC) | CNN | trumpstruth uncached | trumpstruth cached | First mirror |
|---|---|---|---|---|
| 14:55:37 | 1.6 min (file stamp) | about 17 min (from probe-live-check) | 39 min | 1.6 min |
| 16:15:32 | 9.4 min | 3.2 min | not seen in window | 3.2 min |
| 16:54:55 | 2.7 min | 7.6 min | not seen in window | 2.7 min |

CNN's file changed 8 times in the window, 8 to 26 minutes apart. One full 20 MB CNN download was cut short (IncompleteRead).
