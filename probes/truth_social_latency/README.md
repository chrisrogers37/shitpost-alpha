# TEMPORARY: Truth Social source latency probe

> **Remove this directory after the probe run.** It is a one-off measurement for
> choosing a free replacement for ScrapeCreators. Nothing else in the repo imports it,
> it has no tables, and it is not wired into the root `railway.json`.

`ts_probe.py` polls the free mirror sources for 24 hours and logs JSON lines:
every request's HTTP status plus Cloudflare and rate-limit headers, and the first time
each Trump post appears, with `lag_s` = first seen minus the post's `created_at`.
Read-only: no credentials, no database, no S3, no environment variables.

By default it polls only the mirrors (`cnn` every 20 s, `trumpstruth` every 60 s).
The `direct` sources are off until Chris decides whether to poll truthsocial.com;
turning them on is a start-command change: `--sources direct,direct_cf,cnn,trumpstruth`.

| Source | What it hits |
|---|---|
| `direct` | truthsocial.com public statuses API, no auth, plain `urllib` |
| `direct_cf` | same URL via `curl_cffi` Chrome impersonation |
| `cnn` | CNN archive JSON (`ix.cnn.io`) |
| `trumpstruth` | trumpstruth.org RSS |

Polls use ETag conditional requests, so an unchanged feed answers 304 with no body.
The RSS and the direct API (if enabled) are held to one request a minute, well under
the 300-per-window limit the direct API reports.

## Run on Railway
Create a **new, separate** service in the shitpost-alpha project so the live harvester
is untouched:

1. Source: this repo, branch `claude/project-thread-yfvll0`.
2. Root directory: `probes/truth_social_latency`.
3. Config file path: `/probes/truth_social_latency/railway.json` (Railway does not
   follow the root directory for config, and the repo-root `railway.json` must not be
   used here). It sets the start command (`python ts_probe.py poll --hours 24`) and no
   restarts.
4. Do not add any variables. Let it run 24 hours, then export the logs.
5. Delete the service, then delete this directory.

## Read the results

    python ts_probe.py summarize railway-logs.txt

Prints success rate and status codes per source, and median / p90 / max lag over
posts seen during the run.

## Tests
`pytest probes/truth_social_latency` runs offline fixture tests (block, new post,
RSS item without a status ID).
