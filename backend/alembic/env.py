from logging.config import fileConfig
from typing import Literal

from alembic import context
from sqlalchemy import TypeDecorator, create_engine, pool

# app.models registers every model (see its __init__) so autogenerate can see their tables
import app.models  # noqa: F401
from app.config import get_settings
from app.db import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url() -> str:
    """Use an explicitly set sqlalchemy.url (tests do this), else the app's DATABASE_URL"""
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def render_item(type_: str, obj: object, autogen_context: object) -> str | Literal[False]:
    """Autogenerate app column types (TypeDecorators) as their SQL type, not as app imports"""
    if type_ == "type" and isinstance(obj, TypeDecorator):
        return f"sa.{obj.impl_instance!r}"
    return False


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (`alembic upgrade head --sql`)"""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against a live database connection"""
    connectable = create_engine(get_url(), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_item=render_item,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
