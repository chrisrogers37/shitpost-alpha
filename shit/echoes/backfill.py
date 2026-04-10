"""
Backfill embeddings for existing analyzed posts.

Usage:
    python -m shit.echoes.backfill [--batch-size 100]

Also serves as a retry mechanism: any prediction without an embedding
(including those that failed on first attempt) will be picked up.
"""

import argparse

from sqlalchemy import text

from shit.db.sync_session import get_session
from shit.echoes.echo_service import EchoService
from shit.logging import get_service_logger, setup_cli_logging

logger = get_service_logger("echo_backfill")


def backfill_embeddings(batch_size: int = 100) -> int:
    """Embed all existing analyzed posts that don't have embeddings yet.

    Args:
        batch_size: Number of texts to embed per OpenAI API call.

    Returns:
        Total number of embeddings generated.
    """
    with get_session() as session:
        predictions = session.execute(
            text("""
                SELECT p.id, p.shitpost_id, p.signal_id,
                       COALESCE(s.text, ts.text) as post_text
                FROM predictions p
                LEFT JOIN signals s ON s.signal_id = p.signal_id
                LEFT JOIN truth_social_shitposts ts ON ts.shitpost_id = p.shitpost_id
                LEFT JOIN post_embeddings pe ON pe.prediction_id = p.id
                WHERE p.analysis_status = 'completed'
                    AND pe.id IS NULL
                    AND COALESCE(s.text, ts.text) IS NOT NULL
                ORDER BY p.id
            """)
        ).fetchall()

    total = len(predictions)
    if total == 0:
        logger.info("No predictions need embedding")
        return 0

    logger.info(f"Backfilling embeddings for {total} predictions")
    service = EchoService()
    embedded = 0

    for i in range(0, total, batch_size):
        batch = predictions[i : i + batch_size]
        texts = [row[3] for row in batch]

        embeddings = service.embedding_client.embed_batch(texts)

        import hashlib

        from shit.echoes.models import PostEmbedding

        with get_session() as session:
            for j, (pred_id, shitpost_id, signal_id, post_text) in enumerate(batch):
                text_hash = hashlib.sha256(post_text.encode()).hexdigest()
                record = PostEmbedding(
                    prediction_id=pred_id,
                    shitpost_id=shitpost_id,
                    signal_id=signal_id,
                    text_hash=text_hash,
                    embedding=embeddings[j],
                    model=service.embedding_client.model,
                )
                session.add(record)

        embedded += len(batch)
        logger.info(f"Backfilled {min(i + batch_size, total)}/{total} embeddings")

    logger.info(f"Backfill complete: {embedded} embeddings generated")
    return embedded


def main() -> None:
    """CLI entry point."""
    setup_cli_logging(verbose=True)
    parser = argparse.ArgumentParser(description="Backfill post embeddings")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Texts per OpenAI API call (default: 100)",
    )
    args = parser.parse_args()
    backfill_embeddings(batch_size=args.batch_size)


if __name__ == "__main__":
    main()
