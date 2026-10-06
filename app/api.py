from datetime import date
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import bearer, check_login_rate, dummy_hash, get_current_user, hash_password, issue_token, require_roles, revoke_token, verify_password
from app.database import get_db
from app.models import Budget, Category, Role, User
from app.schemas import BudgetIn, BudgetOut, CategoryIn, CategoryOut, ExpenseIn, ExpenseOut, LoginIn, RegisterIn, UserOut
from app.services import BudgetService, ExpenseService, commit_or_conflict

router = APIRouter(prefix="/api")


@router.post("/auth/register", status_code=201)
def register(data: RegisterIn, db: Annotated[Session, Depends(get_db)]) -> dict:
    user = User(name=data.name.strip(), email=str(data.email).lower(), password_hash=hash_password(data.password), role=Role.USER)
    db.add(user)
    commit_or_conflict(db, "Email already exists")
    db.refresh(user)
    return {"data": UserOut.model_validate(user)}


@router.post("/auth/login")
def login(data: LoginIn, request: Request, db: Annotated[Session, Depends(get_db)]) -> dict:
    check_login_rate(request)
    user = db.scalar(select(User).where(func.lower(User.email) == str(data.email).lower()))
    if user is None:
        verify_password(data.password, dummy_hash)
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    return {"data": {"access_token": issue_token(db, user), "token_type": "Bearer", "user": UserOut.model_validate(user)}}


@router.post("/auth/logout", status_code=204)
def logout(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)], _user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> None:
    revoke_token(db, credentials.credentials)


@router.get("/categories")
def categories(_user: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)) -> dict:
    total = db.scalar(select(func.count()).select_from(Category).where(Category.is_active.is_(True))) or 0
    items = db.scalars(select(Category).where(Category.is_active.is_(True)).order_by(Category.name).offset((page - 1) * limit).limit(limit)).all()
    return {"data": [CategoryOut.model_validate(item) for item in items], "meta": {"page": page, "limit": limit, "total": total, "total_pages": ceil(total / limit)}}


@router.post("/categories", status_code=201)
def create_category(data: CategoryIn, admin: Annotated[User, Depends(require_roles(Role.ADMIN))], db: Annotated[Session, Depends(get_db)]) -> dict:
    item = Category(name=data.name.strip(), created_by=admin.id)
    db.add(item)
    commit_or_conflict(db, "Category already exists")
    db.refresh(item)
    return {"data": CategoryOut.model_validate(item)}


@router.get("/expenses")
def list_expenses(actor: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], search: str = Query("", max_length=160), start: date | None = None, end: date | None = None, category_id: int | None = Query(None, ge=1), page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=100)) -> dict:
    return ExpenseService(db).list(actor, search, start, end, category_id, page, limit)


@router.post("/expenses", status_code=201)
def create_expense(data: ExpenseIn, actor: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    return {"data": ExpenseOut.model_validate(ExpenseService(db).create(data, actor))}


@router.get("/expenses/{expense_id}")
def get_expense(expense_id: int, actor: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    return {"data": ExpenseOut.model_validate(ExpenseService(db).get_owned(expense_id, actor))}


@router.put("/expenses/{expense_id}")
def update_expense(expense_id: int, data: ExpenseIn, actor: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    return {"data": ExpenseOut.model_validate(ExpenseService(db).update(expense_id, data, actor))}


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(expense_id: int, actor: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> Response:
    ExpenseService(db).delete(expense_id, actor)
    return Response(status_code=204)


@router.put("/budgets", status_code=200)
def upsert_budget(data: BudgetIn, actor: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    return {"data": BudgetOut.model_validate(BudgetService(db).upsert(data, actor))}


@router.get("/budgets")
def list_budgets(actor: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], year: int = Query(ge=2000, le=2100), month: int = Query(ge=1, le=12)) -> dict:
    items = db.scalars(select(Budget).where(Budget.user_id == actor.id, Budget.month == date(year, month, 1)).order_by(Budget.category_id)).all()
    return {"data": [BudgetOut.model_validate(item) for item in items]}


@router.get("/reports/monthly")
def monthly_report(actor: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], year: int = Query(ge=2000, le=2100), month: int = Query(ge=1, le=12)) -> dict:
    return {"data": BudgetService(db).report(actor, year, month)}


@router.get("/dashboard")
def dashboard(actor: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> dict:
    today = date.today()
    return {"data": BudgetService(db).report(actor, today.year, today.month)}

