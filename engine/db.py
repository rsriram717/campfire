"""Session factory for the engine database."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from engine import config
from engine.models import Base


def make_engine(url: str = None, **kwargs):
    return create_engine(url or config.DATABASE_URL, **kwargs)


def init_db(engine) -> None:
    """Create all tables (dev only; Postgres migrations come in Phase 8)."""
    Base.metadata.create_all(engine)


def make_session_factory(engine) -> sessionmaker:
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
