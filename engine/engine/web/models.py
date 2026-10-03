"""Base response models. Every /api/v1 route returns an ApiResponse (ApiRouter checks)."""

from collections.abc import Iterator
from typing import Any, TypeAliasType, get_args, get_origin
from uuid import UUID

from pydantic import BaseModel, ConfigDict, PlainSerializer, WithJsonSchema, WrapSerializer
from pydantic.fields import ComputedFieldInfo, FieldInfo
from pydantic.json_schema import SkipJsonSchema

ALIASES = ("alias", "validation_alias", "serialization_alias")
SCHEMA_CONFIG = ("json_schema_extra", "json_schema_mode_override", "json_encoders")
OWN_HOOKS = ("__get_pydantic_core_schema__", "__get_pydantic_json_schema__")
MARKERS = (PlainSerializer, WrapSerializer, WithJsonSchema, SkipJsonSchema)
"""Annotated markers that serialize a value their own way, or change its schema."""


class ApiModel(BaseModel):
    """Anything /api/v1 returns, whole or nested. It sends the fields it lists, under their
    own names, as pydantic serializes their types, and its schema says so; a row or dict
    with a field the model doesn't name fails validation instead of passing through.

    So a subclass may not: allow extra fields; take aliases (computed fields' included);
    serialize a value its own way (a model or field serializer, PlainSerializer,
    WrapSerializer, json_encoders); change its schema (json_schema_extra,
    json_schema_mode_override, WithJsonSchema, SkipJsonSchema, its own pydantic hooks); or
    nest a model that isn't an ApiModel. Markers count anywhere in a field's type. A custom
    type's own pydantic hooks are not checked: keep API fields to plain types."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        problem = _problem(cls)
        if problem:
            raise TypeError(f"{cls.__name__}: {problem}")


def _problem(cls: type[ApiModel]) -> str | None:
    config = cls.model_config
    fields: dict[str, FieldInfo | ComputedFieldInfo] = {
        **cls.model_fields,
        **cls.model_computed_fields,
    }
    if config.get("extra") != "forbid":
        return "API models forbid extra fields"
    aliased = [name for name, f in fields.items() if any(getattr(f, a, None) for a in ALIASES)]
    if aliased or config.get("alias_generator"):
        return f"API models take no aliases {aliased}"
    decorators = cls.__pydantic_decorators__
    if (
        decorators.model_serializers
        or decorators.field_serializers
        or any(config.get(key) for key in SCHEMA_CONFIG)
        or any(hook in vars(cls) for hook in OWN_HOOKS)
    ):
        return "API models keep pydantic's serializers and schema"
    for name, field in fields.items():
        if isinstance(field, FieldInfo):
            parts = [*field.metadata, *_parts(field.annotation)]
        else:
            parts = list(_parts(field.return_type))
        if field.json_schema_extra or any(_changes_schema(part) for part in parts):
            return f"API models keep pydantic's serializers and schema ({name})"
        if any(_foreign_model(part) for part in parts):
            return f"API models nest only ApiModels ({name})"
    return None


def _parts(annotation: Any, aliases: frozenset[int] = frozenset()) -> Iterator[Any]:
    """Every type, argument and Annotated marker inside `annotation`, through type aliases
    (each alias once, so a recursive one ends)."""
    yield annotation
    alias = annotation if isinstance(annotation, TypeAliasType) else get_origin(annotation)
    if isinstance(alias, TypeAliasType) and id(alias) not in aliases:
        yield from _parts(alias.__value__, aliases | {id(alias)})
    for arg in get_args(annotation):
        yield from _parts(arg, aliases)


def _changes_schema(part: Any) -> bool:
    return isinstance(part, MARKERS) or (
        isinstance(part, FieldInfo) and bool(part.json_schema_extra)
    )


def _foreign_model(part: Any) -> bool:
    return isinstance(part, type) and issubclass(part, BaseModel) and not issubclass(part, ApiModel)


class ApiResponse(ApiModel):
    """A whole response body. Clients compare stream_id between calls: a new value means
    the engine's database was rebuilt, so ids and cursors they hold no longer apply."""

    stream_id: UUID
