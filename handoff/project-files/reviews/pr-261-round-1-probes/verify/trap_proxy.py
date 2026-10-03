"""A local stand-in for every outside host: listens on 127.0.0.1, logs each request line
(CONNECT host:port for HTTPS through a proxy) and answers 403. Point HTTPS_PROXY and
HTTP_PROXY at it so nothing leaves the sandbox; the log shows what the code tried."""

import socketserver
import sys
from pathlib import Path

LOG = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("trap.log")


class Handler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        line = self.rfile.readline(65536).decode("latin-1").strip()
        with LOG.open("a") as log:
            log.write(line + "\n")
        self.wfile.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("127.0.0.1", int(sys.argv[1])), Handler) as server:
        server.serve_forever()
