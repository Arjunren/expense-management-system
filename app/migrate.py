from pathlib import Path

from sqlalchemy import text

from app.database import engine


def main() -> None:
    folder = Path(__file__).resolve().parent.parent / "migrations"
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(255) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"))
    for path in sorted(folder.glob("*.sql")):
        with engine.begin() as connection:
            if connection.scalar(text("SELECT 1 FROM schema_migrations WHERE version=:version"), {"version": path.name}):
                continue
            for statement in path.read_text(encoding="utf-8").split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)
            connection.execute(text("INSERT INTO schema_migrations(version) VALUES(:version)"), {"version": path.name})
        print(f"applied {path.name}")


if __name__ == "__main__":
    main()

