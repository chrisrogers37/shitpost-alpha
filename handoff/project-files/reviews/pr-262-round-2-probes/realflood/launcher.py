"""Test-only launcher: `python -m engine web` with the PR's test routes mounted."""
import sys

import engine.web.app as appmod
from engine import cli
from tests.web.routes import ProbeRoutes

probe = ProbeRoutes()
orig = appmod.create_app
appmod.create_app = lambda settings, routers=(): orig(settings, [probe.router])  # type: ignore[assignment]
sys.exit(cli.main(["web"]))
