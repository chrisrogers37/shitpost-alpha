"""
PostEmbedding model for storing text embeddings with pgvector.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func

from shit.db.data_models import Base


class PostEmbedding(Base):
    """Stores text embeddings for semantic similarity search."""

    __tablename__ = "post_embeddings"

    id = Column(Integer, primary_key=True)
    prediction_id = Column(
        Integer,
        ForeignKey("predictions.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    shitpost_id = Column(String(255), nullable=True)
    signal_id = Column(String(255), nullable=True)
    text_hash = Column(String(64), nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    model = Column(String(50), nullable=False, default="text-embedding-3-small")
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        src = self.shitpost_id or self.signal_id or "?"
        return f"<PostEmbedding(prediction_id={self.prediction_id}, source={src})>"
