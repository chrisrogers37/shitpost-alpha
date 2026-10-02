"""Base response models. Every /api/v1 route returns an ApiResponse (ApiRouter checks)."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ApiModel(BaseModel):
    """Anything /api/v1 returns, whole or nested. It lists its fields: a row or dict with
    a field the model doesn't name fails validation instead of passing through. Fields go
    out under their own names: aliases are refused, so the schema, a cached body and a
    route's own body all have one shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        aliased = [
            name
            for name, field in cls.model_fields.items()
            if field.alias or field.validation_alias or field.serialization_alias
        ]
        if aliased or cls.model_config.get("alias_generator"):
            raise TypeError(f"{cls.__name__}: API models take no aliases {aliased}")


class ApiResponse(ApiModel):
    """A whole response body. Clients compare stream_id between calls: a new value means
    the engine's database was rebuilt, so ids and cursors they hold no longer apply."""

    stream_id: UUID
