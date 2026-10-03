"""Records claims g and h (scratch tool). Same record format as record_claims.py."""
import json, os, sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
import httpx

OUT = Path(sys.argv[1])
KEEP = ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "content-type")
now = datetime.now(UTC).replace(second=0, microsecond=0)
z = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")
stock = {"feed": "sip", "adjustment": "all", "limit": "10000"}
CALLS = {
    "g_spy_1day_end_16min_ago": ("/v2/stocks/bars", {"symbols": "SPY", "timeframe": "1Day", "start": z(now - timedelta(days=5)), "end": z(now - timedelta(minutes=16))} | stock),
    "h_fb_1day_2021-01": ("/v2/stocks/bars", {"symbols": "FB", "timeframe": "1Day", "start": "2021-01-04T00:00:00Z", "end": "2021-01-09T00:00:00Z"} | stock),
    "h_meta_1day_2021-01": ("/v2/stocks/bars", {"symbols": "META", "timeframe": "1Day", "start": "2021-01-04T00:00:00Z", "end": "2021-01-09T00:00:00Z"} | stock),
}
key, secret = os.environ["ALPACA_API_KEY_ID"], os.environ["ALPACA_API_SECRET_KEY"]
with httpx.Client(base_url="https://data.alpaca.markets", follow_redirects=False, timeout=30) as client:
    auth = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    for name, (path, params) in CALLS.items():
        r = client.get(path, params=params, headers=auth)
        rec = {"recorded_at": z(now), "request": {"path": path, "params": params}, "status": r.status_code,
               "headers": {k: v for k, v in r.headers.items() if k.lower() in KEEP}, "body": r.json()}
        text = json.dumps(rec, indent=1)
        assert key not in text and secret not in text
        (OUT / f"{name}.json").write_text(text)
        bars = [b for v in (rec["body"].get("bars") or {}).values() for b in v]
        print(name, r.status_code, [(b["t"], b["v"]) for b in bars])
