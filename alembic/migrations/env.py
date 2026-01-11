from logging.config import fileConfig
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
import sys
from pathlib import Path
import asyncio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from models.Basic import Base

config = context.config
fileConfig(config.config_file_name)

session_URL = "postgresql+asyncpg://pollux:pollux@session:5432/messenger"
config.set_main_option("sqlalchemy.url", session_URL)

target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(
        url=session_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    engine = create_async_engine(session_URL)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())