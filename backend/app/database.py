from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Resolve DB path relative to this file's directory (backend/app/)
# so it works regardless of the working directory at startup
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_DB = f"sqlite:///{os.path.join(_BASE_DIR, 'zt_exam.db')}"

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DB)

# Fix common Render PostgreSQL URL scheme (postgres:// -> postgresql://)
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

