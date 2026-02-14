"""
Event Type Constants and Fan-Out Configuration

Defines all event types, their consumer groups, and payload schemas.
The CONSUMER_GROUPS mapping drives write-time fan-out in emit_event().
"""


class EventType:
    """Constants for all event types in the pipeline."""

    POSTS_HARVESTED = "posts_harvested"
    SIGNALS_STORED = "signals_stored"
    PREDICTION_CREATED = "prediction_created"
    PRICES_BACKFILLED = "prices_backfilled"


class ConsumerGroup:
    """Constants for all consumer groups."""

    S3_PROCESSOR = "s3_processor"
    ANALYZER = "analyzer"
    MARKET_DATA = "market_data"
    NOTIFICATIONS = "notifications"


# Fan-out map: event_type -> list of consumer groups that receive a copy.
# emit_event() creates one row per consumer group listed here.
CONSUMER_GROUPS: dict[str, list[str]] = {
    EventType.POSTS_HARVESTED: [
        ConsumerGroup.S3_PROCESSOR,
    ],
    EventType.SIGNALS_STORED: [
        ConsumerGroup.ANALYZER,
    ],
    EventType.PREDICTION_CREATED: [
        ConsumerGroup.MARKET_DATA,
        ConsumerGroup.NOTIFICATIONS,
    ],
    EventType.PRICES_BACKFILLED: [
        # Terminal event - no downstream consumers
    ],
}


# Payload documentation (for reference, not enforced at runtime)
PAYLOAD_SCHEMAS: dict[str, dict] = {
    EventType.POSTS_HARVESTED: {
        "s3_keys": "list[str] - S3 keys of harvested posts",
        "source": "str - source name, e.g. 'truth_social'",
        "count": "int - number of posts harvested",
        "mode": "str - harvesting mode (incremental/backfill/range)",
    },
    EventType.SIGNALS_STORED: {
        "signal_ids": "list[str] - signal IDs stored in database",
        "source": "str - source name",
        "count": "int - number of signals stored",
    },
    EventType.PREDICTION_CREATED: {
        "prediction_id": "int - database ID of the prediction",
        "signal_id": "str|None - signal ID if available",
        "shitpost_id": "str|None - shitpost ID if available",
        "assets": "list[str] - ticker symbols",
        "confidence": "float - prediction confidence",
        "analysis_status": "str - completed/bypassed/error",
    },
    EventType.PRICES_BACKFILLED: {
        "symbols": "list[str] - symbols that were backfilled",
        "prediction_id": "int - triggering prediction ID",
        "assets_backfilled": "int - number of assets backfilled",
        "outcomes_calculated": "int - number of outcomes calculated",
    },
}
