from collections.abc import Generator

from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

from src.core.settings import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

session_factory = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> Generator[Session, None, None]:
    with session_factory() as session:
        yield session
