"""Turns the raw recordings into repo fixtures (scratch tool, not repo code).

The repo is public and Alpaca's data stays private, so every number in a bar (o, h, l, c,
v, n, vw) is replaced by a stand-in of the same type; everything else (request, status,
rate-limit headers, keys, bar times, page tokens, error text) is the real answer.
"""
import json, sys
from pathlib import Path

RAW, FIX = Path(sys.argv[1]), Path(sys.argv[2])
RECORDED_AT = "2026-10-02T19:04:00Z"  # the clock the recorder's relative times came from
NUMS = ("o", "h", "l", "c", "v", "n", "vw")

def load(name): return json.loads((RAW / f"{name}.json").read_text())

def stand_in(bar, i, factor=1.0):
    base = 100.0 + i
    out = dict(bar)
    out.update(o=round(base * factor, 2), h=round((base + 1) * factor, 2), l=round((base - 1) * factor, 2),
               c=round((base + 0.5) * factor, 2), vw=round((base + 0.25) * factor, 4))
    v = (1000 + i) / factor
    out["v"] = int(round(v)) if isinstance(bar["v"], int) else round(v, 6)
    out["n"] = 10 + i
    assert set(out) == set(bar)
    return out

def body_with(body, fn, keep=None):
    (symbol, bars), = body["bars"].items()
    total = len(bars)
    new = [fn(b, i) for i, b in enumerate(bars)]
    if keep and total > keep[0] + keep[1]:
        new = new[: keep[0]] + new[-keep[1]:]
    return {"bars": {symbol: new}, "next_page_token": body["next_page_token"]}, total

ORDER = ("t", "o", "h", "l", "c", "v", "n", "vw")

def write(path, content):
    """Indented, with one bar per line."""
    lines = {}
    def mark(obj):
        if isinstance(obj, dict) and "t" in obj and "o" in obj:
            key = f"@@bar{len(lines)}@@"
            lines[key] = json.dumps({k: obj[k] for k in ORDER})
            return key
        if isinstance(obj, dict):
            return {k: mark(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [mark(v) for v in obj]
        return obj
    text = json.dumps(mark(content), indent=2) + "\n"
    for key, line in lines.items():
        text = text.replace(f'"{key}"', line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print(path.name, len(text))

plain = lambda b, i: stand_in(b, i)

# Fixtures the adapter tests use: bodies only.
p1, p2 = load("page_spy_1day_p1"), load("page_spy_1day_p2")
write(FIX / "alpaca_stock_bars_page1.json", body_with(p1["body"], plain)[0])
write(FIX / "alpaca_stock_bars_page2.json", body_with(p2["body"], lambda b, i: stand_in(b, i + 2))[0])
write(FIX / "alpaca_coin_bars.json", body_with(load("coin_btc_1day_2024-01-02")["body"], plain)[0])
write(FIX / "alpaca_error.json", load("b_spy_1min_end_5min_ago")["body"])

# One recorded call per claim.
f_all, f_raw = load("f_nvda_1day_all"), load("f_nvda_1day_raw")
factors = [round(r["c"] / a["c"], 2) for a, r in zip(f_all["body"]["bars"]["NVDA"], f_raw["body"]["bars"]["NVDA"])]
TRIM = (3, 2)  # long answers keep their first three and last two bars
CLAIMS = {
    "a_spy_minutes_2016-01-04": ("a_spy_1min_2016-01-04", plain, TRIM),
    "b_sip_ending_16_minutes_ago": ("b_spy_1min_end_16min_ago", plain, TRIM),
    "b_sip_ending_5_minutes_ago": ("b_spy_1min_end_5min_ago", None, None),
    "d_btc_minutes_2022-02-01": ("d_btc_1min_2022-02-01", plain, TRIM),
    "d_eth_minutes_2022-02-01": ("d_eth_1min_2022-02-01", plain, TRIM),
    "d_btc_first_daily": ("d_btc_1day_first", plain, TRIM),
    "d_eth_first_daily": ("d_eth_1day_first", plain, TRIM),
    "e_meta_june_2022": ("e_meta_1day_2022-06", plain, None),
    "e_fb_june_2022": ("e_fb_1day_2022-06", plain, None),
    "f_nvda_split_all": ("f_nvda_1day_all", plain, None),
    "f_nvda_split_raw": ("f_nvda_1day_raw", lambda b, i: stand_in(b, i, factors[i]), None),
    "g_spy_daily_during_a_session": ("g_spy_1day_end_16min_ago", plain, None),
    "h_fb_january_2021": ("h_fb_1day_2021-01", plain, None),
}
for name, (raw_name, fn, keep) in CLAIMS.items():
    rec = load(raw_name)
    out = {"recorded_at": rec.get("recorded_at", RECORDED_AT), "request": rec["request"], "status": rec["status"], "headers": rec["headers"]}
    if fn is None:
        out["body"] = rec["body"]
    else:
        out["body"], out["bars_returned"] = body_with(rec["body"], fn, keep=keep)
    write(FIX / "alpaca_claims" / f"{name}.json", out)
print("factors", factors)
