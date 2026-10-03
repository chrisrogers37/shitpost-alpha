"""Rebuild probe JSON records from Railway get-logs output (attributes -> dict)."""
import json, sys
out = []
for path in sys.argv[1:]:
    for e in json.load(open(path)).get("deploy", []):
        r = {}
        for a in e.get("attributes", []):
            try:
                r[a["key"]] = json.loads(a["value"])
            except Exception:
                r[a["key"]] = a["value"]
        if not r.get("type"):
            r = {"type": "raw", "ts": e["timestamp"], "message": e["message"], "severity": e.get("severity")}
        out.append(r)
for r in out:
    print(json.dumps(r))
