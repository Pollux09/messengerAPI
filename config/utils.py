import asyncio
import subprocess
import sys
import os
from config.logger import logger
from config.settings import settings


async def init_db() -> None:
    """Инициализация базы данных"""
    try:
        # Ждем, пока база данных станет доступной
        await wait_for_database()

        # Пробуем запустить миграции
        await run_migrations_async()

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # В режиме разработки можно продолжить
        if settings.ENVIRONMENT != "production":
            logger.warning("Continuing without migrations in development mode")
        else:
            raise


async def wait_for_database(retries: int = 10, delay: int = 3):
    """Ожидание готовности базы данных"""
    from sqlalchemy import text
    from config.db import session_helper

    for i in range(retries):
        try:
            async with session_helper.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                logger.info("✅ Database is ready")
                return
        except Exception as e:
            logger.warning(f"Database not ready (attempt {i + 1}/{retries}): {e}")
            if i < retries - 1:
                await asyncio.sleep(delay)

    raise ConnectionError(f"Database not available after {retries} attempts")


async def run_migrations_async():
    """Запуск миграций"""
    try:
        logger.info("🚀 Starting migrations...")

        # Запускаем через текущий Python интерпретатор
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            cwd="/app",  # Убедитесь, что это правильная директория
            env={**os.environ, "PYTHONPATH": "/app"}
        )

        logger.info(f"Migration stdout:\n{result.stdout}")

        if result.returncode != 0:
            logger.error(f"Migration stderr:\n{result.stderr}")

            # Попробуем создать таблицы напрямую
            logger.info("Trying to create tables directly...")
            await create_tables_directly()
            return

        logger.info("✅ Migrations completed successfully!")

    except Exception as e:
        logger.error(f"Migration error: {e}")
        raise


async def create_tables_directly():
    """Создание таблиц напрямую через SQLAlchemy"""
    try:
        from config.db import Base, session_helper

        async with session_helper.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Tables created directly via SQLAlchemy")

    except Exception as e:
        logger.error(f"Error creating tables directly: {e}")
        raise