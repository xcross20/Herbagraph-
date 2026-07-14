import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

import app.models  # noqa: F401  (registers all ORM models on Base.metadata)
from app.config import settings
from app.core.database_url import prepare_asyncpg_url
from app.database import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ConfigParser treats % as interpolation syntax — escape URL-encoded password chars (%40, etc.)
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_item=_render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def _render_item(type_, obj, autogen_context):
    """Ensure custom column types (e.g. GUID) render with a resolvable import."""
    if type_ == "type" and obj.__class__.__module__ == "app.models.mixins":
        autogen_context.imports.add("import app.models.mixins")
        return f"app.models.mixins.{obj.__class__.__name__}(length={obj.length})"
    return False


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, render_item=_render_item
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    db_url = settings.database_url
    if db_url.startswith("postgresql"):
        db_url, connect_args = prepare_asyncpg_url(db_url)
    else:
        connect_args = {}
    connectable = create_async_engine(
        db_url,
        connect_args=connect_args,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
