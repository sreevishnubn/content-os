"""Apply ContentOS PostgreSQL migrations from the migrations directory."""

from pathlib import Path

from sqlalchemy import create_engine, text

from app.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required for production migrations")

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    migration_dir = Path(__file__).resolve().parents[1] / "migrations"
    with engine.begin() as connection:
        for path in sorted(migration_dir.glob("*.sql")):
            statements = [s.strip() for s in path.read_text(encoding="utf-8").split(";") if s.strip()]
            for statement in statements:
                connection.execute(text(statement))
            print(f"Applied {path.name}")


if __name__ == "__main__":
    main()
