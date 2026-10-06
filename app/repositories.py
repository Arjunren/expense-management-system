from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Expense


class ExpenseRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, user_id: int, search: str, start: date | None, end: date | None, category_id: int | None, page: int, limit: int):
        query = select(Expense).where(Expense.user_id == user_id)
        count = select(func.count()).select_from(Expense).where(Expense.user_id == user_id)
        conditions = []
        if search:
            conditions.append(or_(Expense.merchant.ilike(f"%{search}%"), Expense.description.ilike(f"%{search}%")))
        if start:
            conditions.append(Expense.spent_on >= start)
        if end:
            conditions.append(Expense.spent_on <= end)
        if category_id:
            conditions.append(Expense.category_id == category_id)
        query, count = query.where(*conditions), count.where(*conditions)
        items = self.db.scalars(query.order_by(Expense.spent_on.desc(), Expense.id.desc()).offset((page - 1) * limit).limit(limit)).all()
        return list(items), self.db.scalar(count) or 0

