"""Verify-only trap proxy on 127.0.0.1: logs each request's first line and answers 403."""
import socketserver
import sys

LOG = sys.argv[2]


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline(4096).decode("latin-1").strip()
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f"ATTEMPT {line}\n")
        self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")


socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("127.0.0.1", int(sys.argv[1])), Handler) as server:
    server.serve_forever()
