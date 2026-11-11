"""Response shapes shared by every resource: errors, pages and the new/edit form data"""

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


class ErrorBody(BaseModel):
    """Every error response: a human-readable `detail` and a stable machine-readable `code`"""

    detail: str
    code: str
    # Field-level problems, only on 422 validation errors
    errors: list[dict[str, Any]] | None = None


class ReadModel(BaseModel):
    """Base for `XRead` schemas, which are built straight from ORM objects"""

    model_config = ConfigDict(from_attributes=True)


def _drop_default(schema: dict[str, Any]) -> None:
    schema.pop("default", None)


def omitted() -> Any:
    """Default for an `XUpdate` field that may be left out but not sent as null, e.g.
    `name: Name = omitted()`. Fields that can be cleared are typed `X | None = None` instead"""
    return Field(default=None, json_schema_extra=_drop_default)


class UpdateModel(BaseModel):
    """Base for `XUpdate` (PATCH) bodies: only the fields sent are changed"""

    def apply_to(self, item: object, exclude: set[str] | None = None) -> None:
        """Set the fields sent on `item`, except those in `exclude` (e.g. `position`, which
        moves the item with `place()` instead)"""
        for field, value in self.model_dump(exclude_unset=True, exclude=exclude).items():
            setattr(item, field, value)


# Where an ordered child goes among its siblings, from 0. One past the end (or more) puts it
# last; see app/models/ordering.py
Position = Annotated[int, Field(ge=0)]


def two_places(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


# A weight as stored (NUMERIC(6, 2)): 0 to 9999.99, kept to two decimal places so responses
# read "102.50" whether the client sent 102.5 or "102.50"
Weight = Annotated[Decimal, Field(ge=0, max_digits=6, decimal_places=2), AfterValidator(two_places)]


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
