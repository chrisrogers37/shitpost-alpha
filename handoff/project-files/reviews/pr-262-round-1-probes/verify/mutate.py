"""Mutation tests for PR #262's safety guards. Each mutation reverts one guard in the
mutation worktree, runs the tests that should catch it, then restores the file with git.
A mutation is CAUGHT when pytest exits non-zero."""

import subprocess
import sys
from pathlib import Path

MUT = Path(sys.argv[1])  # <worktree>/engine
PY = "/home/user/engine-venv-262/bin/python"
CLEAN = str(Path(__file__).parent / "clean.sh")

# (id, property, file, old, new, tests)
MUTATIONS = [
    ("M1", "web role: grant prices", "engine/migrate.py",
     '"app": "USAGE",\n}', '"app": "USAGE",\n    "prices": "USAGE",\n    "prices.*": "SELECT",\n}',
     ["tests/web/test_web_role.py"]),
    ("M2", "web role: grant writes on engine.*", "engine/migrate.py",
     '"engine.*": "SELECT",', '"engine.*": "SELECT, INSERT, UPDATE, DELETE",',
     ["tests/web/test_web_role.py"]),
    ("M3", "web role: grant CREATE on app", "engine/migrate.py",
     '"app": "USAGE",', '"app": "USAGE",\n    "app.*": "SELECT",',
     ["tests/web/test_web_role.py"]),
    ("M4", "web role: tests connect as the superuser", "tests/web/conftest.py",
     "    return url.render_as_string(hide_password=False)", "    return database_url",
     ["tests/web/test_web_role.py"]),
    ("M5", "statement timeout listener removed", "engine/web/db.py",
     '    event.listen(db.sync_engine, "connect", _set_statement_timeout, insert=True)\n', "",
     ["tests/web/test_web_role.py"]),
    ("M6", "explicit fields: models accept extra fields", "engine/web/models.py",
     'extra="forbid"', 'extra="ignore"',
     ["tests/web/test_api_conventions.py"]),
    ("M7", "explicit fields: ApiRouter stops refusing non-ApiResponse models", "engine/web/router.py",
     "        if not (isinstance(model, type) and issubclass(model, ApiResponse)):", "        if False:",
     ["tests/web/test_api_conventions.py"]),
    ("M8", "no prices: walker stops following $ref", "tests/web/test_no_prices.py",
     "            if isinstance(ref, str) and ref not in seen:", "            if False:",
     ["tests/web/test_no_prices.py"]),
    ("M9", "no prices: no camelCase split", "tests/web/test_no_prices.py",
     r're.split(r"_|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", name)', 're.split(r"_", name)',
     ["tests/web/test_no_prices.py"]),
    ("M10", "rate key: leftmost entry (visitor-written)", "engine/web/ratelimit.py",
     "address = _parse(entries[-trusted_hops])", "address = _parse(entries[0])",
     ["tests/web/test_rate_limit.py"]),
    ("M11", "rate key: header ignored, socket only", "engine/web/ratelimit.py",
     "    if len(entries) >= trusted_hops:", "    if False:",
     ["tests/web/test_rate_limit.py"]),
    ("M12", "rate key: one shared bucket", "engine/web/ratelimit.py",
     "wait = self.buckets.take(client_address(scope, self.header, self.trusted_hops))", 'wait = self.buckets.take("all")',
     ["tests/web/test_rate_limit.py"]),
    ("M13", "rate limit: /healthz limited", "engine/web/ratelimit.py",
     'UNLIMITED_PATHS = frozenset({"/healthz"})', "UNLIMITED_PATHS: frozenset[str] = frozenset()",
     ["tests/web/test_rate_limit.py"]),
    ("M14", "rate key: uvicorn proxy headers on", "engine/cli.py",
     "proxy_headers=False,", "proxy_headers=True,",
     ["tests/web/test_server.py"]),
    ("M15", "rate limit: no Retry-After", "engine/web/ratelimit.py",
     "scope[\"path\"], \"rate_limited\", \"Too many requests\", headers=retry_after", "scope[\"path\"], \"rate_limited\", \"Too many requests\"",
     ["tests/web/test_rate_limit.py"]),
    ("M16", "errors: unhandled exception not caught by ResponsePolicy", "engine/web/policy.py",
     "        except Exception:\n            log.exception", "        except ZeroDivisionError:\n            log.exception",
     ["tests/web/test_api_conventions.py"]),
    ("M17", "errors: 503 message leaks the driver error", "engine/web/errors.py",
     '"unavailable", "The database is unavailable")', '"unavailable", f"The database is unavailable: {exc}")',
     ["tests/web/test_health.py"]),
    ("M18", "errors: 404 message from Starlette", "engine/web/errors.py",
     'message = "Not found" if code == "not_found" else str(exc.detail)', "message = str(exc.detail)",
     ["tests/web/test_api_conventions.py"]),
    ("M19", "errors: FastAPI's 422 back", "engine/web/errors.py",
     "    app.add_exception_handler(RequestValidationError, bad_request)\n", "",
     ["tests/web/test_paging_and_cache.py"]),
    ("M20", "errors: OperationalError unhandled (500 not 503)", "engine/web/errors.py",
     "    app.add_exception_handler(OperationalError, unavailable)  # refused, lost, timed out\n", "",
     ["tests/web/test_health.py"]),
    ("M21", "CORS: every method", "engine/web/policy.py",
     'if method == "GET" and path.startswith("/api/v1/"):', 'if path.startswith("/api/v1/"):',
     ["tests/web/test_api_conventions.py"]),
    ("M22", "CORS: every path", "engine/web/policy.py",
     'if method == "GET" and path.startswith("/api/v1/"):', 'if method == "GET":',
     ["tests/web/test_api_conventions.py"]),
    ("M23", "CORS: credentials allowed", "engine/web/policy.py",
     'OPEN_CORS = {"Access-Control-Allow-Origin": "*"}', 'OPEN_CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Credentials": "true"}',
     ["tests/web/test_api_conventions.py"]),
    ("M24", "headers: HSTS gains includeSubDomains; preload", "engine/web/policy.py",
     '"Strict-Transport-Security": "max-age=31536000",', '"Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",',
     ["tests/web"]),
    ("M25", "headers: Referrer-Policy dropped", "engine/web/policy.py",
     '    "Referrer-Policy": "strict-origin-when-cross-origin",\n', "",
     ["tests/web"]),
    ("M26", "headers: CSP weakened", "engine/web/policy.py",
     "\"default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; \"", "\"default-src *; \"",
     ["tests/web"]),
    ("M27", "access log: visitor address logged", "engine/web/policy.py",
     'log.info("%s %s %s %.0fms", method, printable, status or "-", elapsed_ms)', 'log.info("%s %s %s %s %.0fms", scope.get("client"), method, printable, status or "-", elapsed_ms)',
     ["tests/web/test_api_conventions.py", "tests/web/test_server.py"]),
    ("M28", "web command builds the engine's Settings first", "engine/cli.py",
     '    configure_logging()\n    if args.command == "web":', '    configure_logging()\n    Settings()\n    if args.command == "web":',
     ["tests/web/test_server.py"]),
    ("M29", "healthz timeout 2 s -> 10 s", "engine/web/health.py",
     "HEALTH_TIMEOUT_SECONDS = 2.0", "HEALTH_TIMEOUT_SECONDS = 10.0",
     ["tests/web/test_health.py"]),
    ("M30", "healthz cacheable", "engine/web/health.py",
     'headers={"Cache-Control": "no-store"}', "headers={}",
     ["tests/web/test_health.py"]),
    ("M31", "stream_id read every request", "engine/web/stream.py",
     "if self._value is None or self._clock() - self._read_at >= self._ttl:", "if True:",
     ["tests/web/test_api_conventions.py"]),
    ("M32", "cursor: any spelling accepted", "engine/web/paging.py",
     "        or encode_cursor(tuple(key)) != cursor  # one spelling per key\n", "",
     ["tests/web/test_paging_and_cache.py"]),
    ("M33", "cache: key ignores the query string", "engine/web/cache.py",
     'key = f"{request.url.path}?{request.url.query}"', "key = request.url.path",
     ["tests/web/test_paging_and_cache.py"]),
    ("M34", "cache: never expires", "engine/web/cache.py",
     "if hit is not None and hit[0] > now:", "if hit is not None:",
     ["tests/web/test_paging_and_cache.py"]),
    ("M35", "docs pages back on", "engine/web/app.py",
     "docs_url=None,", 'docs_url="/docs",',
     ["tests/web/test_api_conventions.py"]),
    ("M36", "limit max 100 -> 1000", "engine/web/paging.py",
     "MAX_LIMIT = 100", "MAX_LIMIT = 1000",
     ["tests/web/test_paging_and_cache.py"]),
]


def run(mid: str, prop: str, rel: str, old: str, new: str, tests: list[str]) -> str:
    path = MUT / rel
    text = path.read_text()
    if text.count(old) != 1:
        return f"{mid} | {prop} | SKIPPED: anchor found {text.count(old)} times"
    path.write_text(text.replace(old, new))
    try:
        proc = subprocess.run(
            [CLEAN, "env", f"PYTHONPATH={MUT}", PY, "-m", "pytest", "-p", "no:cacheprovider", "-q", "-x", *tests],
            cwd=MUT, capture_output=True, text=True, timeout=600,
        )
    finally:
        subprocess.run(["git", "checkout", "--", rel], cwd=MUT, check=True)
    last = (proc.stdout.strip().splitlines() or ["?"])[-1]
    failed = [line for line in proc.stdout.splitlines() if line.startswith("FAILED") or line.startswith("ERROR")]
    verdict = "CAUGHT" if proc.returncode != 0 else "SURVIVED"
    detail = failed[0][:150] if failed else ""
    return f"{mid} | {prop} | {verdict} | {last} | {detail}"


if __name__ == "__main__":
    only = set(sys.argv[2:])
    for m in MUTATIONS:
        if only and m[0] not in only:
            continue
        print(run(*m), flush=True)
    status = subprocess.run(["git", "status", "--short"], cwd=MUT, capture_output=True, text=True).stdout
    print("worktree clean after mutations:", status.strip() == "" or status)
