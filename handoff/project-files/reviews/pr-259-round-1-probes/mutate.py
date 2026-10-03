import subprocess, sys, pathlib, os
root = pathlib.Path("mut/engine")
MUTS = {
 "M1 cnn no If-None-Match": ("engine/feeds/cnn.py", 'conditional=True,', 'conditional=False,'),
 "M2 swap errors/blocks counters": ("engine/feeds/live.py", "errors=int(not blocked), blocks=int(blocked)", "errors=int(blocked), blocks=int(not blocked)"),
 "M3 start ignores stored dark_since": ("engine/feeds/live.py", "            self.dark_since = (\n                await conn.execute(select(engine_meta.c.feeds_dark_since))\n            ).scalar_one_or_none()", "            pass"),
 "M4 not_modified never counted": ("engine/feeds/live.py", "not_modified=int(read.not_modified),", "not_modified=0,"),
 "M5 scrapecreators pages with wrong param": ("engine/feeds/mastodon.py", 'params["next_max_id"] = max_id', 'params["max_id"] = max_id'),
 "M6 answered polls not counted": ("engine/feeds/live.py", "                polls=1,\n                not_modified", "                polls=0,\n                not_modified"),
 "M7 sighting time = poll start of other feed (no first_seen update)": ("engine/feeds/store.py", "    if sighted - added:", "    if False:"),
 "M8 dark not cleared in db": ("engine/feeds/live.py", "            await conn.execute(update(engine_meta).values(feeds_dark_since=None))", "            pass"),
 "M9 trumpstruth no cache-bust": ("engine/feeds/trumpstruth.py", 'params={"t": str(int(time.time()))}', 'params={}'),
 "M10 direct exclude_replies dropped": ("engine/feeds/mastodon.py", '{"exclude_replies": "true", "limit": PAGE_SIZE}', '{"limit": PAGE_SIZE}'),
}
env = dict(os.environ, PYTHONPATH=str(root.resolve()))
for name, (path, old, new) in MUTS.items():
    f = root / path
    src = f.read_text()
    assert src.count(old) == 1, (name, src.count(old))
    f.write_text(src.replace(old, new))
    try:
        r = subprocess.run([ "/home/user/engine-venv-259/bin/pytest", "-q", "-x", "-p", "no:cacheprovider",
                             "tests/test_feed_mapping.py", "tests/test_live.py", "tests/test_store.py", "tests/test_history.py", "tests/test_posts.py"],
                           cwd=root, env=env, capture_output=True, text=True, timeout=600)
        last = r.stdout.strip().splitlines()[-1]
        print(f"{name}: {'SURVIVED' if r.returncode == 0 else 'killed'} ({last})")
    finally:
        f.write_text(src)
