"""Verify-only socket guard: logs and refuses any connection or lookup that isn't loopback
or a Unix socket. The log path comes from VERIFY_GUARD_LOG."""
import os
import socket

_LOG = os.environ.get("VERIFY_GUARD_LOG")
_LOCAL = {"127.0.0.1", "::1", "localhost", "0.0.0.0"}


def _note(kind, target):
    if _LOG:
        with open(_LOG, "a", encoding="utf-8") as f:
            f.write(f"{os.getpid()} {kind} {target!r}\n")


def _local(address):
    if isinstance(address, (str, bytes)):  # a Unix socket path
        return True
    host = address[0] if isinstance(address, tuple) and address else address
    return str(host) in _LOCAL or str(host).startswith("127.")


_connect = socket.socket.connect
_connect_ex = socket.socket.connect_ex
_getaddrinfo = socket.getaddrinfo


def connect(self, address):
    if self.family != getattr(socket, "AF_UNIX", None) and not _local(address):
        _note("connect", address)
        raise OSError("verify guard: outbound connection refused")
    return _connect(self, address)


def connect_ex(self, address):
    if self.family != getattr(socket, "AF_UNIX", None) and not _local(address):
        _note("connect_ex", address)
        raise OSError("verify guard: outbound connection refused")
    return _connect_ex(self, address)


def getaddrinfo(host, *args, **kwargs):
    if host is not None and not _local((host,)):
        _note("getaddrinfo", host)
        raise socket.gaierror("verify guard: lookup refused")
    return _getaddrinfo(host, *args, **kwargs)


socket.socket.connect = connect
socket.socket.connect_ex = connect_ex
socket.getaddrinfo = getaddrinfo
if _LOG:
    with open(_LOG + ".loaded", "a", encoding="utf-8") as f:
        f.write(f"{os.getpid()} guard loaded\n")
