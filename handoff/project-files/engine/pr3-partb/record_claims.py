"""Records the PR 3 Alpaca claim calls (scratch tool, not repo code).

Keys come from ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY in the environment and go in
headers only. Each answer is saved as {request: {path, params}, status, headers (rate-limit
and content-type only), body}. No request headers are saved.
"""
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
    "a_spy_1min_2016-01-04": ("/v2/stocks/bars", {"symbols": "SPY", "timeframe": "1Min", "start": "2016-01-04T00:00:00Z", "end": "2016-01-05T00:00:00Z"} | stock),
    "b_spy_1min_end_16min_ago": ("/v2/stocks/bars", {"symbols": "SPY", "timeframe": "1Min", "start": z(now - timedelta(minutes=46)), "end": z(now - timedelta(minutes=16))} | stock),
    "b_spy_1min_end_5min_ago": ("/v2/stocks/bars", {"symbols": "SPY", "timeframe": "1Min", "start": z(now - timedelta(minutes=35)), "end": z(now - timedelta(minutes=5))} | stock),
    "d_btc_1min_2022-02-01": ("/v1beta3/crypto/us/bars", {"symbols": "BTC/USD", "timeframe": "1Min", "start": "2022-02-01T00:00:00Z", "end": "2022-02-02T00:00:00Z", "limit": "10000"}),
    "d_eth_1min_2022-02-01": ("/v1beta3/crypto/us/bars", {"symbols": "ETH/USD", "timeframe": "1Min", "start": "2022-02-01T00:00:00Z", "end": "2022-02-02T00:00:00Z", "limit": "10000"}),
    "d_btc_1day_first": ("/v1beta3/crypto/us/bars", {"symbols": "BTC/USD", "timeframe": "1Day", "start": "2010-01-01T00:00:00Z", "end": "2023-01-01T00:00:00Z", "limit": "10000"}),
    "d_eth_1day_first": ("/v1beta3/crypto/us/bars", {"symbols": "ETH/USD", "timeframe": "1Day", "start": "2010-01-01T00:00:00Z", "end": "2023-01-01T00:00:00Z", "limit": "10000"}),
    "e_meta_1day_2022-06": ("/v2/stocks/bars", {"symbols": "META", "timeframe": "1Day", "start": "2022-06-01T00:00:00Z", "end": "2022-06-16T00:00:00Z"} | stock),
    "e_fb_1day_2022-06": ("/v2/stocks/bars", {"symbols": "FB", "timeframe": "1Day", "start": "2022-06-01T00:00:00Z", "end": "2022-06-16T00:00:00Z"} | stock),
    "e_fb_1day_2022-06_asof": ("/v2/stocks/bars", {"symbols": "FB", "timeframe": "1Day", "start": "2022-06-01T00:00:00Z", "end": "2022-06-16T00:00:00Z", "asof": "2022-06-01"} | stock),
    "f_nvda_1day_all": ("/v2/stocks/bars", {"symbols": "NVDA", "timeframe": "1Day", "start": "2024-06-05T00:00:00Z", "end": "2024-06-15T00:00:00Z"} | stock),
    "f_nvda_1day_raw": ("/v2/stocks/bars", {"symbols": "NVDA", "timeframe": "1Day", "start": "2024-06-05T00:00:00Z", "end": "2024-06-15T00:00:00Z"} | stock | {"adjustment": "raw"}),
    "page_spy_1day_p1": ("/v2/stocks/bars", {"symbols": "SPY", "timeframe": "1Day", "start": "2024-01-02T00:00:00Z", "end": "2024-01-05T00:00:00Z", "feed": "sip", "adjustment": "all", "limit": "2"}),
    "coin_btc_1day_2024-01-02": ("/v1beta3/crypto/us/bars", {"symbols": "BTC/USD", "timeframe": "1Day", "start": "2024-01-02T00:00:00Z", "end": "2024-01-03T00:00:00Z", "limit": "10000"}),
}

key, secret = os.environ["ALPACA_API_KEY_ID"], os.environ["ALPACA_API_SECRET_KEY"]
with httpx.Client(base_url="https://data.alpaca.markets", follow_redirects=False, timeout=30) as client:
    auth = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    for name, (path, params) in CALLS.items():
        r = client.get(path, params=params, headers=auth)
        rec = {"request": {"path": path, "params": params}, "status": r.status_code,
               "headers": {k: v for k, v in r.headers.items() if k.lower() in KEEP}}
        try:
            rec["body"] = r.json()
        except ValueError:
            rec["body_text"] = r.text[:500]
        text = json.dumps(rec, indent=1)
        assert key not in text and secret not in text
        (OUT / f"{name}.json").write_text(text)
        n = sum(len(v) for v in ((rec.get("body") or {}).get("bars") or {}).values()) if isinstance(rec.get("body"), dict) else None
        print(f"{name}: HTTP {r.status_code} bars={n} token={'yes' if isinstance(rec.get('body'), dict) and rec['body'].get('next_page_token') else 'no'}")
    # page 2 of the paging fixture
    p1 = json.loads((OUT / "page_spy_1day_p1.json").read_text())
    path, params = CALLS["page_spy_1day_p1"]
    params = params | {"page_token": p1["body"]["next_page_token"]}
    r = client.get(path, params=params, headers=auth)
    rec = {"request": {"path": path, "params": params}, "status": r.status_code, "headers": {k: v for k, v in r.headers.items() if k.lower() in KEEP}, "body": r.json()}
    text = json.dumps(rec, indent=1); assert key not in text and secret not in text
    (OUT / "page_spy_1day_p2.json").write_text(text)
    print(f"page_spy_1day_p2: HTTP {r.status_code}")
