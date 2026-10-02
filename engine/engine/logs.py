"""Logging setup for the engine's processes."""

import logging


def configure_logging() -> None:
    """Log INFO and up to stderr, one line per record."""
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s", force=True
    )
    # httpx logs every request at INFO; the feeds poll several times a minute.
    logging.getLogger("httpx").setLevel(logging.WARNING)
