from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

try:
    import psycopg2.extensions
    import numpy as np

    def _adapt_np_float(val):
        return psycopg2.extensions.Float(float(val))

    def _adapt_np_int(val):
        return psycopg2.extensions.Int(int(val))

    for _t in (np.float64, np.float32, np.float16, getattr(np, "float128", np.float64)):
        psycopg2.extensions.register_adapter(_t, _adapt_np_float)
    for _t in (np.int64, np.int32, np.int16, np.int8, np.uint64, np.uint32, np.uint16, np.uint8):
        psycopg2.extensions.register_adapter(_t, _adapt_np_int)
except Exception:
    pass

settings = get_settings()

engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=300,
    connect_args={"options": "-c search_path=public"},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
