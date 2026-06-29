from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite
)


# Enforce foreign keys on every connection (SQLite disables them by default)
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables. Called once at startup."""
    from backend.models import user, query_log  # noqa: F401 — imports register models
    Base.metadata.create_all(bind=engine)
