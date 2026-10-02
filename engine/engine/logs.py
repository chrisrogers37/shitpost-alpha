"""Logging setup for the engine's processes."""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True
    )
    # httpx logs every request at INFO; the feeds poll several times a minute.
    logging.getLogger("httpx").setLevel(logging.WARNING)
