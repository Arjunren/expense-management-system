from datetime import date
from decimal import Decimal
from math import ceil

from fastapi import HTTPException, status
from sqlalchemy import extract, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ActivityLog, Budget, Category, Expense, User
from app.repositories import ExpenseRepository
from app.schemas import BudgetIn, ExpenseIn, ExpenseOut


def commit_or_conflict(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, message) from None


class ExpenseService:
    def __init__(self, db: Session):
        self.db = db

    def _category(self, category_id: int) -> Category:
        item = self.db.get(Category, category_id)
        if item is None or not item.is_active:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "category_id must reference an active category")
        return item

    def create(self, data: ExpenseIn, actor: User) -> Expense:
        self._category(data.category_id)
        item = Expense(**data.model_dump(), user_id=actor.id, created_by=actor.id, updated_by=actor.id)
        self.db.add(item)
        self.db.flush()
        self.db.add(ActivityLog(user_id=actor.id, action="CREATE", entity_type="EXPENSE", entity_id=item.id))
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_owned(self, expense_id: int, actor: User) -> Expense:
        item = self.db.get(Expense, expense_id)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
        if item.user_id != actor.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot access another user's expense")
        return item

    def update(self, expense_id: int, data: ExpenseIn, actor: User) -> Expense:
        item = self.get_owned(expense_id, actor)
        self._category(data.category_id)
        for field, value in data.model_dump().items():
            setattr(item, field, value)
        item.updated_by = actor.id
        self.db.add(ActivityLog(user_id=actor.id, action="UPDATE", entity_type="EXPENSE", entity_id=item.id))
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, expense_id: int, actor: User) -> None:
        item = self.get_owned(expense_id, actor)
        self.db.delete(item)
        self.db.add(ActivityLog(user_id=actor.id, action="DELETE", entity_type="EXPENSE", entity_id=item.id))
        self.db.commit()

    def list(self, actor: User, search: str, start: date | None, end: date | None, category_id: int | None, page: int, limit: int) -> dict:
        if start and end and start > end:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "start must not be after end")
        items, total = ExpenseRepository(self.db).list(actor.id, search.strip(), start, end, category_id, page, limit)
        return {"data": [ExpenseOut.model_validate(item) for item in items], "meta": {"page": page, "limit": limit, "total": total, "total_pages": ceil(total / limit)}}


class BudgetService:
    def __init__(self, db: Session):
        self.db = db

    def upsert(self, data: BudgetIn, actor: User) -> Budget:
        ExpenseService(self.db)._category(data.category_id)
        item = self.db.scalar(select(Budget).where(Budget.user_id == actor.id, Budget.category_id == data.category_id, Budget.month == data.month))
        if item is None:
            item = Budget(**data.model_dump(), user_id=actor.id, created_by=actor.id, updated_by=actor.id)
            self.db.add(item)
        else:
            item.amount, item.updated_by = data.amount, actor.id
        commit_or_conflict(self.db, "Budget already exists")
        self.db.refresh(item)
        return item

    def report(self, actor: User, year: int, month: int) -> dict:
        total = self.db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.user_id == actor.id, extract("year", Expense.spent_on) == year, extract("month", Expense.spent_on) == month)) or Decimal("0")
        rows = self.db.execute(select(Category.id, Category.name, func.coalesce(func.sum(Expense.amount), 0)).join(Expense, Expense.category_id == Category.id).where(Expense.user_id == actor.id, extract("year", Expense.spent_on) == year, extract("month", Expense.spent_on) == month).group_by(Category.id, Category.name).order_by(Category.name)).all()
        budget_rows = self.db.scalars(select(Budget).where(Budget.user_id == actor.id, Budget.month == date(year, month, 1))).all()
        budgets = {item.category_id: item.amount for item in budget_rows}
        return {"year": year, "month": month, "total_spent": total, "categories": [{"category_id": row[0], "name": row[1], "spent": row[2], "budget": budgets.get(row[0]), "remaining": budgets[row[0]] - row[2] if row[0] in budgets else None} for row in rows]}

