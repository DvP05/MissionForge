"""Common API contract models and the response envelope (architecture 6.2, 11.1)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.capitalize() for part in tail)


class ContractModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class ApiMeta(ContractModel):
    request_id: str
    schema_version: Literal["1.0"] = "1.0"
    generated_at: datetime | None = None
    source_status: Literal["live", "cached", "demo"] | None = None


class ApiError(ContractModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, Any] | None = None


class ApiResult[T](ContractModel):
    ok: bool
    data: T | None = None
    error: ApiError | None = None
    meta: ApiMeta
