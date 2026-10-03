"""Verify-only: every number in the report files against every stand-in price served."""
import json, re, sys
prices = {float(x) for x in open(sys.argv[1])}
lo, hi = min(prices), max(prices)
r2 = {round(p, 2) for p in prices}
for path in sys.argv[2:]:
    text = open(path, encoding="utf-8").read()
    nums = [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*\.?\d*", text)]
    big = sorted({n for n in nums if abs(n) >= 100})
    exact = sorted({n for n in nums if n in prices or (n != int(n) and round(n, 2) in r2)})
    links = re.findall(r"[a-z][a-z0-9+.-]*://\S+|www\.\S+|\]\([^)]*\)", text, re.I)
    print(path.rsplit("/", 1)[-1], f"numbers={len(nums)} >=100: {big[:40]}")
    print("  in stand-in price range", f"[{lo:.2f},{hi:.2f}]:", sorted({n for n in nums if lo * 0.5 <= abs(n) <= hi * 1.5})[:20])
    print("  equal to a served price:", exact[:20])
    print("  links:", links)
    print("  'price' mentions:", len(re.findall(r"price", text, re.I)))
