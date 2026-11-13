"""Deep-immutability building blocks for contracts that must never change after creation.

- `FrozenContract`: a ContractModel that is frozen (assignment raises) and revalidates
  nested instances, so a model never aliases a caller-owned object.
- `FrozenMap[V]`: an immutable, hashable `Mapping[str, V]`. It validates exactly like
  `dict[str, V]` (same JSON schema, values fully validated, e.g. NaN rejected) and
  serialises back to a plain JSON object.

Frozen models use `tuple[...]` for collections (JSON schema: array) and `FrozenMap` for maps.
"""

from collections.abc import Iterator, Mapping
from typing import Any, TypeVar, get_args

from pydantic import ConfigDict, GetCoreSchemaHandler
from pydantic_core import core_schema

from app.schemas.api import ContractModel

V_co = TypeVar("V_co", covariant=True)


class FrozenMap(Mapping[str, V_co]):
    __slots__ = ("_data", "_hash")

    def __init__(self, data: Mapping[str, V_co] | None = None) -> None:
        self._data: dict[str, V_co] = dict(data or {})
        self._hash: int | None = None

    def __getitem__(self, key: str) -> V_co:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __hash__(self) -> int:
        if self._hash is None:
            self._hash = hash(frozenset(self._data.items()))
        return self._hash

    def __repr__(self) -> str:
        return f"FrozenMap({self._data!r})"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source: Any, handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        args = get_args(source)
        value_type: Any = args[0] if args else Any
        dict_schema = handler.generate_schema(dict[str, value_type])
        return core_schema.no_info_after_validator_function(
            cls,
            dict_schema,
            serialization=core_schema.plain_serializer_function_ser_schema(
                dict, return_schema=dict_schema
            ),
        )


class FrozenContract(ContractModel):
    model_config = ConfigDict(frozen=True, revalidate_instances="always")
