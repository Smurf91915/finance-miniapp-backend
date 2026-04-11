from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import require_database_url


engine = create_engine(require_database_url(), future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
