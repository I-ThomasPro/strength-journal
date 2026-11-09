"""Response shapes shared by every resource: errors, pages and the new/edit form data"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    """Every error response: a human-readable `detail` and a stable machine-readable `code`"""

    detail: str
    code: str
    # Field-level problems, only on 422 validation errors
    errors: list[dict[str, Any]] | None = None


class ReadModel(BaseModel):
    """Base for `XRead` schemas, which are built straight from ORM objects"""

    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    """One page of an `index`; `total` counts every match, not just this page"""

    items: list[T]
    total: int


class NewForm[T](BaseModel):
    """What a `new` action returns: default values plus the allowed values of fixed fields"""

    defaults: T
    options: dict[str, list[str]] = Field(default_factory=dict)


class EditForm[T](BaseModel):
    """What an `edit` action returns: current values plus the allowed values of fixed fields"""

    values: T
    options: dict[str, list[str]] = Field(default_factory=dict)


def enum_options(**fields: type[StrEnum]) -> dict[str, list[str]]:
    """Form `options` for fixed-value fields, e.g. `enum_options(weight_unit=WeightUnit)`"""
    return {field: [member.value for member in enum] for field, enum in fields.items()}
