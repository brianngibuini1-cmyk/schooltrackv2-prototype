"""Request schemas and server-side validation.

The browser never sends prices, totals or reference numbers: it sends what the
user typed, and the server validates it, prices it and assigns the reference.
``extra="forbid"`` makes that contract explicit — an attempt to inject
``total_cents`` or ``reference`` is a 422 rather than silently ignored.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CATEGORY_LABELS: dict[str, str] = {
    "primary": "Primary",
    "jss": "Junior Secondary (JSS)",
}
CATEGORY_ORDER = ("primary", "jss")

PAYMENT_METHOD_LABELS: dict[str, str] = {
    "cash": "Cash",
    "mpesa": "M-Pesa",
    "bank_transfer": "Bank transfer",
    "cheque": "Cheque",
    "other": "Other",
}
PAYMENT_METHOD_ORDER = ("cash", "mpesa", "bank_transfer", "cheque", "other")

STATUS_LABELS: dict[str, str] = {
    "pending": "Pending approval",
    "approved": "Approved",
    "rejected": "Rejected",
}
STATUS_ORDER = ("pending", "approved", "rejected")

MAX_ITEMS = 50
MAX_UNIT_COST = Decimal("10000000.00")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9()\-\s]{5,39}$")


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SupplierCreate(ApiModel):
    name: str = Field(min_length=2, max_length=120)
    contact_person: str = Field(default="", max_length=120)
    phone: str = Field(default="", max_length=40)
    email: str = Field(default="", max_length=160)
    address: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=500)

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter the supplier name.")
        return value

    @field_validator("phone")
    @classmethod
    def phone_must_look_valid(cls, value: str) -> str:
        if value and not PHONE_RE.match(value):
            raise ValueError(
                "Enter a valid phone number, for example 0712 345 678."
            )
        return value

    @field_validator("email")
    @classmethod
    def email_must_look_valid(cls, value: str) -> str:
        if value and not EMAIL_RE.match(value):
            raise ValueError("Enter a valid email address.")
        return value


class LineItemCreate(ApiModel):
    description: str = Field(min_length=2, max_length=160)
    quantity: int = Field(ge=1, le=100_000)
    unit_cost: Decimal = Field(
        gt=Decimal("0"),
        le=MAX_UNIT_COST,
        max_digits=12,
        decimal_places=2,
    )


class PurchaseCreate(ApiModel):
    purchase_date: date
    supplier_id: int = Field(ge=1)
    category: Literal["primary", "jss"]
    payment_method: Literal["cash", "mpesa", "bank_transfer", "cheque", "other"]
    invoice_number: str = Field(default="", max_length=60)
    status: Literal["pending", "approved"] = "pending"
    notes: str = Field(default="", max_length=500)
    items: list[LineItemCreate] = Field(min_length=1, max_length=MAX_ITEMS)

    @field_validator("purchase_date")
    @classmethod
    def purchase_date_must_be_plausible(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("Purchase date cannot be in the future.")
        if value < date(2000, 1, 1):
            raise ValueError("Purchase date is too far in the past.")
        return value


class PurchaseStatusUpdate(ApiModel):
    status: Literal["pending", "approved", "rejected"]


def category_label(value: str) -> str:
    return CATEGORY_LABELS.get(value, value)


def payment_method_label(value: str) -> str:
    return PAYMENT_METHOD_LABELS.get(value, value)


def status_label(value: str) -> str:
    return STATUS_LABELS.get(value, value)
