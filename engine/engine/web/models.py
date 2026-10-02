"""Base response models. Every /api/v1 route returns an ApiResponse (create_app checks)."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Anything /api/v1 returns, whole or nested. It lists its fields: a row or dict with
    a field the model doesn't name fails validation instead of passing through."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ApiResponse(ApiModel):
    """A whole response body. Clients compare stream_id between calls: a new value means
    the engine's database was rebuilt, so ids and cursors they hold no longer apply."""

    stream_id: UUID
