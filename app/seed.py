from sqlalchemy import select

from app.auth import hash_password
from app.database import SessionLocal
from app.models import Category, Role, User


def main() -> None:
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == "admin@example.com"))
        if admin is None:
            admin = User(name="Development Admin", email="admin@example.com", password_hash=hash_password("AdminPassword123!"), role=Role.ADMIN)
            db.add(admin)
            db.flush()
        if db.scalar(select(User).where(User.email == "user@example.com")) is None:
            db.add(User(name="Development User", email="user@example.com", password_hash=hash_password("UserPassword123!"), role=Role.USER))
        for name in ("Food", "Housing", "Transport", "Utilities", "Other"):
            if db.scalar(select(Category).where(Category.name == name)) is None:
                db.add(Category(name=name, created_by=admin.id))
        db.commit()
    print("development seed complete")


if __name__ == "__main__":
    main()

