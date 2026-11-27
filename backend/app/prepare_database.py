"""Prepare a fresh hosted database once; never generate live-looking demo rows."""
import os
import subprocess
import sys
from sqlalchemy import text
from app.core.db import engine


def main():
    with engine.begin() as connection:
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS postgis'))
        connection.execute(text('CREATE EXTENSION IF NOT EXISTS pgcrypto'))
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], check=True)
    for module in ('seed_regions','seed_airports','seed_study_regions','seed_exposure_demo'):
        subprocess.run([sys.executable, '-m', 'app.data.' + module], check=True)
    print('Database schema and attributed reference data prepared')


if __name__ == '__main__':
    main()
