from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models import Role


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    name: str
    role: Role
    is_active: bool


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    is_active: bool


class ExpenseIn(BaseModel):
    category_id: int = Field(ge=1)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    spent_on: date
    merchant: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    category_id: int
    amount: Decimal
    spent_on: date
    merchant: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class BudgetIn(BaseModel):
    category_id: int = Field(ge=1)
    month: date
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    @field_validator("month")
    @classmethod
    def first_day(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("month must be the first day of a month")
        return value


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    category_id: int
    month: date
    amount: Decimal

