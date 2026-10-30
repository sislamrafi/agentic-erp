"""Database engine. Uses SQLAlchemy so swapping DATABASE_URL to Postgres is all that's needed."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

_url = DATABASE_URL
if _url.startswith("sqlite:///./"):
    from .config import BASE_DIR
    _url = f"sqlite:///{BASE_DIR / _url[len('sqlite:///./'):]}"

_is_sqlite = _url.startswith("sqlite")
engine = create_engine(
    _url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
