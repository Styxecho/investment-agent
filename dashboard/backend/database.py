"""
Database connection module
Reuse the existing SQLAlchemy engine from the main project
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dashboard.backend.config import settings

# Create engine
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False}  # Required for SQLite
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for FastAPI to get DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
