import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base


def get_database_url() -> str:
    # SQLite file lives inside the project directory for easy deployment.
    db_path = os.getenv("SQLITE_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "outreach.sqlite"))
    db_path = os.path.abspath(db_path)
    return f"sqlite:///{db_path}"


engine = create_engine(
    get_database_url(),
    connect_args={"check_same_thread": False} if get_database_url().startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

