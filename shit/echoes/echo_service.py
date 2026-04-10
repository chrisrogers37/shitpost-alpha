"""
EchoService — Historical similarity search and outcome aggregation.

Embeds post text, stores embeddings in pgvector, finds similar past posts,
and aggregates their realized market outcomes.
"""

import hashlib
from typing import Optional

from sqlalchemy import text as sql_text

from shit.db.sync_session import get_session
from shit.llm.embeddings import EmbeddingClient
from shit.logging import get_service_logger

logger = get_service_logger("echo_service")

EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_SIMILARITY_THRESHOLD = 0.65
DEFAULT_MATCH_LIMIT = 5


class EchoService:
    """Manages post embeddings and historical similarity search.

    Usage:
        service = EchoService()
        service.embed_and_store(prediction_id=123, text="...", shitpost_id="abc")
        matches = service.find_similar_posts(embedding, limit=5)
        echoes = service.aggregate_echoes(matches, timeframe="t7")
    """

    def __init__(self, embedding_client: Optional[EmbeddingClient] = None):
        self.embedding_client = embedding_client or EmbeddingClient(
            model=EMBEDDING_MODEL
        )

    def embed_and_store(
        self,
        prediction_id: int,
        text: str,
        shitpost_id: str | None = None,
        signal_id: str | None = None,
    ) -> bool:
        """Generate embedding for a post and store it.

        Returns True if stored, False if error or already exists.
        """
        if not text or not text.strip():
            logger.debug(f"Skipping empty text for prediction {prediction_id}")
            return False

        from shit.echoes.models import PostEmbedding

        with get_session() as session:
            existing = (
                session.query(PostEmbedding)
                .filter(PostEmbedding.prediction_id == prediction_id)
                .first()
            )
            if existing:
                logger.debug(f"Embedding already exists for prediction {prediction_id}")
                return False

        embedding = self.embedding_client.embed(text)

        with get_session() as session:
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            record = PostEmbedding(
                prediction_id=prediction_id,
                shitpost_id=shitpost_id,
                signal_id=signal_id,
                text_hash=text_hash,
                embedding=embedding,
                model=EMBEDDING_MODEL,
            )
            session.add(record)

        logger.info(f"Stored embedding for prediction {prediction_id}")
        return True

    def get_embedding(self, prediction_id: int) -> Optional[list[float]]:
        """Retrieve the stored embedding for a prediction."""
        from shit.echoes.models import PostEmbedding

        with get_session() as session:
            record = (
                session.query(PostEmbedding)
                .filter(PostEmbedding.prediction_id == prediction_id)
                .first()
            )
            if record:
                return list(record.embedding)
        return None

    def find_similar_posts(
        self,
        embedding: list[float],
        limit: int = DEFAULT_MATCH_LIMIT,
        min_similarity: float = DEFAULT_SIMILARITY_THRESHOLD,
        exclude_prediction_id: int | None = None,
    ) -> list[dict]:
        """Find the most similar historical posts by embedding cosine similarity.

        Args:
            embedding: The query embedding vector.
            limit: Maximum number of matches to return.
            min_similarity: Minimum cosine similarity threshold (0-1).
            exclude_prediction_id: Exclude this prediction from results.

        Returns:
            List of dicts with prediction_id, similarity, text preview, etc.
        """
        max_distance = 1.0 - min_similarity

        query = sql_text("""
            SELECT
                pe.prediction_id,
                pe.shitpost_id,
                pe.signal_id,
                1 - (pe.embedding <=> :query_vec) AS similarity,
                p.assets,
                p.market_impact,
                p.confidence,
                p.thesis,
                p.post_timestamp
            FROM post_embeddings pe
            JOIN predictions p ON p.id = pe.prediction_id
            WHERE pe.prediction_id != COALESCE(:exclude_id, -1)
                AND p.analysis_status = 'completed'
                AND (pe.embedding <=> :query_vec) <= :max_dist
            ORDER BY pe.embedding <=> :query_vec
            LIMIT :lim
        """)

        with get_session() as session:
            result = session.execute(
                query,
                {
                    "query_vec": str(embedding),
                    "exclude_id": exclude_prediction_id,
                    "max_dist": max_distance,
                    "lim": limit,
                },
            )

            matches = []
            for row in result.fetchall():
                matches.append(
                    {
                        "prediction_id": row[0],
                        "shitpost_id": row[1],
                        "signal_id": row[2],
                        "similarity": round(float(row[3]), 4),
                        "assets": row[4],
                        "market_impact": row[5],
                        "confidence": row[6],
                        "thesis": row[7],
                        "post_timestamp": row[8],
                    }
                )

        return matches

    def aggregate_echoes(
        self,
        matches: list[dict],
        timeframe: str = "t7",
    ) -> dict:
        """Aggregate outcomes from similar historical posts.

        Args:
            matches: List of match dicts from find_similar_posts().
            timeframe: Which timeframe to aggregate ("t1", "t3", "t7", "t30").

        Returns:
            Aggregated echo statistics dict.
        """
        if not matches:
            return {"count": 0, "timeframe": timeframe, "matches": []}

        prediction_ids = [m["prediction_id"] for m in matches]

        from shit.market_data.models import PredictionOutcome

        with get_session() as session:
            outcomes = (
                session.query(PredictionOutcome)
                .filter(PredictionOutcome.prediction_id.in_(prediction_ids))
                .all()
            )

        outcomes_by_pred: dict[int, list] = {}
        for o in outcomes:
            outcomes_by_pred.setdefault(o.prediction_id, []).append(o)

        returns: list[float] = []
        correct_count = 0
        incorrect_count = 0
        pnl_values: list[float] = []
        match_details = []

        for match in matches:
            pred_outcomes = outcomes_by_pred.get(match["prediction_id"], [])
            for o in pred_outcomes:
                ret = getattr(o, f"return_{timeframe}", None)
                corr = getattr(o, f"correct_{timeframe}", None)
                pnl = getattr(o, f"pnl_{timeframe}", None)

                if ret is not None:
                    returns.append(ret)
                if corr is True:
                    correct_count += 1
                elif corr is False:
                    incorrect_count += 1
                if pnl is not None:
                    pnl_values.append(pnl)

            match_details.append(
                {
                    "prediction_id": match["prediction_id"],
                    "similarity": match["similarity"],
                    "assets": match.get("assets", []),
                    "thesis": (match.get("thesis") or "")[:100],
                    "post_timestamp": match.get("post_timestamp"),
                    "outcomes": [
                        {
                            "symbol": o.symbol,
                            f"return_{timeframe}": getattr(
                                o, f"return_{timeframe}", None
                            ),
                            f"correct_{timeframe}": getattr(
                                o, f"correct_{timeframe}", None
                            ),
                        }
                        for o in pred_outcomes
                    ],
                }
            )

        evaluated = correct_count + incorrect_count
        return {
            "count": len(matches),
            "timeframe": timeframe,
            "avg_return": round(sum(returns) / len(returns), 4) if returns else None,
            "median_return": (
                round(sorted(returns)[len(returns) // 2], 4) if returns else None
            ),
            "win_rate": (
                round(correct_count / evaluated, 4) if evaluated > 0 else None
            ),
            "correct": correct_count,
            "incorrect": incorrect_count,
            "pending": len(matches) - evaluated,
            "avg_pnl": (
                round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else None
            ),
            "matches": match_details,
        }
