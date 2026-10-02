"""Operator messages. Only logs for now; the notification plan sends them later."""

import logging

log = logging.getLogger(__name__)


async def notify_operator(kind: str, text: str) -> None:
    """Tell the operator something needs a human. `kind` is a short machine-readable tag."""
    log.warning("operator notice [%s] %s", kind, text, extra={"operator_kind": kind})
