"""Create the source-isolated demonstration once, preserving live records."""
import random
from sqlalchemy import text
from app.core.db import engine
from app.data.demo_dataset import generate
if __name__=='__main__':
    with engine.connect() as db:
        exists=db.execute(text("SELECT EXISTS (SELECT 1 FROM flight_observations WHERE source='demo_dataset')")).scalar()
    if not exists:generate(random.Random(42))
