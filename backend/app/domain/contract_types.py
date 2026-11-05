"""Shared, I/O-free validation and immutable JSON values for wire contracts."""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from types import MappingProxyType
from typing import Annotated, TypeAlias

from pydantic import AwareDatetime, BeforeValidator, ConfigDict, Field, JsonValue
from pydantic import BaseModel, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


Identifier: TypeAlias = Annotated[str, Field(strict=True, min_length=1)]
PositiveInt: TypeAlias = Annotated[int, Field(strict=True, gt=0)]
NonNegativeInt: TypeAlias = Annotated[int, Field(strict=True, ge=0)]


def _timestamp_input(value: object) -> object:
    if not isinstance(value, (str, datetime)):
        raise ValueError("timestamp must be an ISO-8601 string or datetime")
    return value


UtcTimestamp: TypeAlias = Annotated[AwareDatetime, BeforeValidator(_timestamp_input)]


class ContractModel(BaseModel):
    """Reject unknown fields and freeze assignments on validated DTOs."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)


type FrozenJsonValue = (
    str | int | float | bool | None | tuple[FrozenJsonValue, ...] | FrozenJsonObject
)


def _freeze_json(value: object, ancestors: set[int]) -> FrozenJsonValue:
    if value is None or type(value) in (str, int, bool):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("JSON numbers must be finite")
        return value
    if isinstance(value, FrozenJsonObject):
        return value
    if isinstance(value, (Mapping, list, tuple)):
        if id(value) in ancestors:
            raise ValueError("JSON values must not contain cycles")
        ancestors.add(id(value))
        try:
            if isinstance(value, Mapping):
                return FrozenJsonObject._from_mapping(value, ancestors)
            return tuple(_freeze_json(item, ancestors) for item in value)
        finally:
            ancestors.remove(id(value))
    raise ValueError(f"unsupported JSON value: {type(value).__name__}")


def _thaw_json(value: FrozenJsonValue) -> JsonValue:
    if isinstance(value, FrozenJsonObject):
        return value.to_dict()
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


@dataclass(frozen=True, slots=True, init=False, eq=False)
class FrozenJsonObject(Mapping[str, FrozenJsonValue]):
    """Own a recursive immutable copy; serialization returns ordinary JSON objects."""

    _data: Mapping[str, FrozenJsonValue] = field(repr=False)

    def __init__(self, value: Mapping[str, object] | None = None) -> None:
        source = {} if value is None else value
        if not isinstance(source, Mapping):
            raise ValueError("payload must be a JSON object")
        frozen = self._from_mapping(source, {id(source)})
        object.__setattr__(self, "_data", frozen._data)

    @classmethod
    def _from_mapping(cls, value: Mapping[object, object], ancestors: set[int]) -> FrozenJsonObject:
        copied: dict[str, FrozenJsonValue] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("JSON object keys must be strings")
            copied[key] = _freeze_json(item, ancestors)
        result = object.__new__(cls)
        object.__setattr__(result, "_data", MappingProxyType(copied))
        return result

    def __getitem__(self, key: str) -> FrozenJsonValue:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __hash__(self) -> int:
        return hash(tuple(sorted(self._data.items())))

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a detached mutable copy suitable for JSONB or transport."""
        return {key: _thaw_json(value) for key, value in self._data.items()}

    @classmethod
    def __get_pydantic_core_schema__(cls, source: object, handler: GetCoreSchemaHandler) -> CoreSchema:
        def validate(value: object) -> FrozenJsonObject:
            if isinstance(value, cls):
                return value
            if not isinstance(value, Mapping):
                raise ValueError("payload must be a JSON object")
            return cls(value)

        return core_schema.no_info_plain_validator_function(
            validate,
            json_schema_input_schema=handler.generate_schema(dict[str, JsonValue]),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda value: value.to_dict(),
                return_schema=handler.generate_schema(dict[str, JsonValue]),
            ),
        )


def as_utc(value: datetime) -> datetime:
    """AwareDatetime validation runs before this normalization step."""
    return value.astimezone(timezone.utc)
