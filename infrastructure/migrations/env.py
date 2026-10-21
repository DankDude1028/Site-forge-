from logging.config import fileConfig
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from siteforge.db import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
url = os.environ.get("SITEFORGE_DATABASE_URL") or os.environ.get("DATABASE_URL")
if url:
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
target_metadata = Base.metadata


def offline():
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def online():
    engine = engine_from_config(config.get_section(config.config_ini_section, {}),
                                prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        if connection.dialect.name == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


offline() if context.is_offline_mode() else online()
