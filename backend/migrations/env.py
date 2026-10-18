from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.config import settings
from src.database import Base
from src.model_registry import import_models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

import_models()
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url") or settings.db_url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection")
    if connectable is None:
        section = config.get_section(config.config_ini_section, {})
        section["sqlalchemy.url"] = (
            config.get_main_option("sqlalchemy.url") or settings.db_url
        )
        connectable = engine_from_config(section, poolclass=pool.NullPool)
        with connectable.connect() as connection:
            _run(connection)
    else:
        _run(connectable)


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
