from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models import Category, Role, User
from app.schemas import BudgetIn, ExpenseIn
from app.services import BudgetService, ExpenseService


def user(db, email="user@example.com"):
    item = User(name="User", email=email, password_hash="unused", role=Role.USER)
    db.add(item)
    db.commit()
    return item


def category(db, actor):
    item = Category(name="Food", created_by=actor.id)
    db.add(item)
    db.commit()
    return item


def test_expense_crud_and_ownership(db):
    owner, other = user(db), user(db, "other@example.com")
    group = category(db, owner)
    service = ExpenseService(db)
    item = service.create(ExpenseIn(category_id=group.id, amount=Decimal("12.50"), spent_on=date(2026, 10, 2), merchant="Cafe"), owner)
    assert service.get_owned(item.id, owner).merchant == "Cafe"
    with pytest.raises(HTTPException) as error:
        service.get_owned(item.id, other)
    assert error.value.status_code == 403


def test_budget_requires_first_day():
    with pytest.raises(ValueError):
        BudgetIn(category_id=1, month=date(2026, 10, 2), amount=Decimal("100"))


def test_monthly_report_tracks_remaining(db):
    actor = user(db)
    group = category(db, actor)
    BudgetService(db).upsert(BudgetIn(category_id=group.id, month=date(2026, 10, 1), amount=Decimal("100")), actor)
    ExpenseService(db).create(ExpenseIn(category_id=group.id, amount=Decimal("25"), spent_on=date(2026, 10, 3), merchant="Market"), actor)
    report = BudgetService(db).report(actor, 2026, 10)
    assert report["total_spent"] == Decimal("25.00")
    assert report["categories"][0]["remaining"] == Decimal("75.00")

