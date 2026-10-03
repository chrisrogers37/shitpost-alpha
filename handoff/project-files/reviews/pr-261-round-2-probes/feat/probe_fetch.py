"""fetch_model against mock transports: mid-stream drop, 404, Ctrl-C, headers on redirect,
already-there short circuit, file modes. No network."""
import hashlib, os, stat, tempfile
from pathlib import Path
import httpx
from engine.extract.similarity import ModelPin, fetch_model, ModelMissing
from engine.settings import Settings

FILES = {"onnx/model.onnx": b"x" * 300_000, "tokenizer.json": b"{}"}
def pin(): return ModelPin("BAAI/bge-small-en-v1.5", "abc123", {p: hashlib.sha256(b).hexdigest() for p, b in FILES.items()}, "cls", 512, 384)
seen = []
class Dropping(httpx.SyncByteStream):
    def __init__(self, body, exc): self.body, self.exc = body, exc
    def __iter__(self):
        yield self.body[:1000]
        raise self.exc
def transport(mode):
    def route(req):
        seen.append((req.url.host, dict(req.headers)))
        if req.url.host == "huggingface.co":
            name = req.url.path.split("/resolve/abc123/", 1)[1]
            return httpx.Response(302, headers={"location": f"https://cas-bridge.xethub.hf.co/x/{name}?X-Amz-Signature=sig"})
        name = req.url.path.removeprefix("/x/")
        if mode == "404" and name == "tokenizer.json":
            return httpx.Response(404)
        if mode == "drop" and name == "onnx/model.onnx":
            return httpx.Response(200, stream=Dropping(FILES[name], httpx.ReadError("connection reset")))
        if mode == "ctrlc" and name == "onnx/model.onnx":
            return httpx.Response(200, stream=Dropping(FILES[name], KeyboardInterrupt()))
        return httpx.Response(200, content=FILES[name])
    return httpx.MockTransport(route)
def files_in(d): return sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file())
for mode in ("drop", "404", "ctrlc", "ok"):
    root = Path(tempfile.mkdtemp(dir=os.environ["SPROOT"]))
    s = Settings(model_dir=root, database_url="postgresql+asyncpg://nobody@127.0.0.1:1/none")
    seen.clear()
    try:
        hosts = fetch_model(s, pin(), transport(mode), say=lambda l: None)
        print(mode, "ok hosts", sorted(hosts))
    except BaseException as e:
        print(mode, "raised", type(e).__name__, str(e)[:120])
    print("   left on disk:", files_in(root))
    if mode == "ok":
        d = pin().directory(root)
        print("   modes:", {p: oct(stat.S_IMODE((d / p).stat().st_mode)) for p in FILES})
        hdrs = {h: sorted(k for k in hd if k not in ("host",)) for h, hd in seen}
        print("   headers per host:", hdrs)
        print("   UA:", seen[0][1]["user-agent"])
