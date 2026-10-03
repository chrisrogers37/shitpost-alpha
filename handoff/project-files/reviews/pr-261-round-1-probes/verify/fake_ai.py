"""A local stand-in for the three AI providers on 127.0.0.1 (verify only). It answers
OpenAI-style chat completions at /v1 and /xai/v1 and Anthropic messages at /anthropic,
choosing the answer from markers in the post text:

- "Apple"    -> Apple, AAPL, explicit, market link
- "Nucor"    -> Nucor, NUE, implied, market link (a ticker not in the book)
- "AUTHFAIL" -> OpenAI answers 401 with the request's key echoed in the message
- "SLOWXAI"  -> xAI waits 17 s before answering (past the 15 s deadline)
- else       -> no market link, no instruments

Each request is logged (path, model, which key header came and its last 4 characters,
temperature, the structured-output setting) to the log file; keys are never logged whole.
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LOG = Path(sys.argv[2])


def answer(text: str) -> dict[str, object]:
    if "Apple" in text:
        items = [{"name": "Apple", "ticker": "AAPL", "asset": "stock", "link": "explicit",
                  "why": "named"}]
        return {"market_link": True, "instruments": items}
    if "Nucor" in text:
        items = [{"name": "Nucor", "ticker": "NUE", "asset": "stock", "link": "implied",
                  "why": "steel"}]
        return {"market_link": True, "instruments": items}
    return {"market_link": False, "instruments": []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        auth = self.headers.get("authorization") or ""
        xkey = self.headers.get("x-api-key") or ""
        key = auth.removeprefix("Bearer ") or xkey
        if self.path.startswith("/anthropic"):
            user = body["messages"][0]["content"]
            structured = body.get("output_config")
        else:
            user = body["messages"][1]["content"]
            structured = body.get("response_format")
        with LOG.open("a") as log:
            log.write(json.dumps({
                "path": self.path, "model": body.get("model"),
                "key_header": "authorization" if auth else ("x-api-key" if xkey else None),
                "key_tail": key[-4:], "temperature": body.get("temperature"),
                "structured": structured is not None, "max_tokens": body.get("max_tokens")
                or body.get("max_completion_tokens"), "user": user[:60],
            }) + "\n")
        if "AUTHFAIL" in user and self.path.startswith("/v1"):
            return self.send(401, {"error": {"message": f"Incorrect API key provided: {key}",
                                             "type": "invalid_request_error"}})
        if "SLOWXAI" in user and self.path.startswith("/xai"):
            time.sleep(17)
        text = json.dumps(answer(user))
        if self.path.startswith("/anthropic"):
            return self.send(200, {
                "id": "msg_fake", "type": "message", "role": "assistant", "model": body["model"],
                "content": [{"type": "text", "text": text}], "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 900, "output_tokens": 60,
                          "cache_read_input_tokens": 100, "cache_creation_input_tokens": 0},
            })
        return self.send(200, {
            "id": "chatcmpl-fake", "object": "chat.completion", "created": 1, "model": body["model"],
            "choices": [{"index": 0, "finish_reason": "stop", "logprobs": None,
                         "message": {"role": "assistant", "content": text, "refusal": None}}],
            "usage": {"prompt_tokens": 1000, "completion_tokens": 60, "total_tokens": 1060,
                      "prompt_tokens_details": {"cached_tokens": 0}},
        })

    def send(self, status: int, payload: dict[str, object]) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), Handler).serve_forever()
