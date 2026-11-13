"""Creates the database in DATABASE_URL if it doesn't exist yet, for the end-to-end tests.
The global setup runs it with the backend's environment:
`uv run python ../frontend/e2e/create_database.py` from backend/"""

import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

url = make_url(os.environ["DATABASE_URL"])
name = url.database
# Connect to the server's maintenance database, outside a transaction: CREATE DATABASE can't
# run inside one
engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with engine.connect() as connection:
    exists = connection.scalar(
        text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}
    )
    if not exists:
        quoted = connection.dialect.identifier_preparer.quote(name)
        connection.execute(text(f"CREATE DATABASE {quoted}"))
        print(f"Created the database {name}")
engine.dispose()
