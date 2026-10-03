"""Mirror lag poller (planning measurement only; mirrors only, never truthsocial.com).

Every CNN_EVERY s: conditional GET on the CNN archive (If-None-Match); on change, Range 0-32767
and parse the newest posts. Every RSS_EVERY s: GET trumpstruth RSS. For each status ID first seen
per source, log created_at (decoded from the ID: Mastodon IDs carry ms << 16) and lag_s.
"""
import datetime as dt, json, re, sys, time, urllib.request

CNN = "https://ix.cnn.io/data/truth-social/truth_archive.json"
RSS = "https://www.trumpstruth.org/feed"
CNN_EVERY, RSS_EVERY = 20, 30
UA = {"User-Agent": "shitpost-alpha-planning-lag-probe/0.1"}
out = open(sys.argv[1], "a", buffering=1)
hours = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

def now(): return dt.datetime.now(dt.UTC)
def id_time(i): return dt.datetime.fromtimestamp((int(i) >> 16) / 1000, dt.UTC)
def log(**kw): out.write(json.dumps({"t": now().isoformat(), **kw}) + "\n")

def fetch(url, headers):
    req = urllib.request.Request(url, headers={**UA, **headers})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), b""
    except Exception as e:
        return None, {"error": repr(e)}, b""

seen = {"cnn": set(), "rss": set(), "rss_fresh": set()}
first = {"cnn": True, "rss": True, "rss_fresh": True}
etag = None
last_cnn = last_rss = 0
end = time.time() + hours * 3600
while time.time() < end:
    t = time.time()
    if t - last_cnn >= CNN_EVERY:
        last_cnn = t
        st, h, _ = fetch(CNN, {"If-None-Match": etag} if etag else {})
        if st == 200 or (st and st != 304 and etag is None):
            st2, h2, body = fetch(CNN, {"Range": "bytes=0-32767", "Accept-Encoding": "identity"})
            etag = h.get("ETag") or h.get("etag") or h2.get("ETag")
            lm = h2.get("Last-Modified")
            log(src="cnn", ev="version", status=st, range_status=st2, last_modified=lm, etag=etag)
            ids = re.findall(r'"id":\s*"(\d{15,})"', body.decode("utf-8", "replace"))
            for i in ids:
                if i not in seen["cnn"]:
                    seen["cnn"].add(i)
                    if not first["cnn"]:
                        ct = id_time(i)
                        log(src="cnn", ev="new", id=i, created_at=ct.isoformat(), lag_s=round((now() - ct).total_seconds(), 1), last_modified=lm)
            first["cnn"] = False
        elif st != 304:
            log(src="cnn", ev="error", status=st, info=str(h.get("error", ""))[:200])
    if t - last_rss >= RSS_EVERY:
        last_rss = t
        for name, url in (("rss", RSS), ("rss_fresh", RSS + "?t=" + str(int(t)))):
            st, h, body = fetch(url, {})
            if st != 200:
                log(src=name, ev="error", status=st, info=str(h.get("error", ""))[:200]); continue
            ids = re.findall(r"<truth:originalId>(\d+)</truth:originalId>", body.decode("utf-8", "replace"))
            for i in ids:
                if i not in seen[name]:
                    seen[name].add(i)
                    if not first[name]:
                        ct = id_time(i)
                        log(src=name, ev="new", id=i, created_at=ct.isoformat(), lag_s=round((now() - ct).total_seconds(), 1), age=h.get("age") or h.get("Age"), cache=h.get("cf-cache-status") or h.get("CF-Cache-Status"))
            if first[name]:
                log(src=name, ev="start", n=len(ids), newest=id_time(max(ids, key=int)).isoformat() if ids else None, age=h.get("age") or h.get("Age"), cache=h.get("cf-cache-status") or h.get("CF-Cache-Status"))
            first[name] = False
    time.sleep(2)
log(ev="done")
