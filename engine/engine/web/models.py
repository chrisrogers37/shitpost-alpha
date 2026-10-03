"""Base response models. Every /api/v1 route returns an ApiResponse (ApiRouter checks)."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

ALIASES = ("alias", "validation_alias", "serialization_alias")


class ApiModel(BaseModel):
    """Anything /api/v1 returns, whole or nested. It sends exactly the fields it lists,
    under their own names, so the schema shows every field: a row or dict with a field the
    model doesn't name fails validation instead of passing through, and a subclass may not
    allow extra fields, take aliases (computed fields' included) or replace the model's
    serializer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        fields = list(cls.model_fields.items()) + list(cls.model_computed_fields.items())
        aliased = [n for n, field in fields if any(getattr(field, a, None) for a in ALIASES)]
        if aliased or cls.model_config.get("alias_generator"):
            raise TypeError(f"{cls.__name__}: API models take no aliases {aliased}")
        if cls.model_config.get("extra") != "forbid":
            raise TypeError(f"{cls.__name__}: API models forbid extra fields")
        if cls.__pydantic_decorators__.model_serializers:
            raise TypeError(f"{cls.__name__}: API models keep pydantic's serializer")


class ApiResponse(ApiModel):
    """A whole response body. Clients compare stream_id between calls: a new value means
    the engine's database was rebuilt, so ids and cursors they hold no longer apply."""

    stream_id: UUID
