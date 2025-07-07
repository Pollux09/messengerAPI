from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+asyncpg://pollux:pollux@db:5432/messenger"

# Создаём асинхронный движок SQLAlchemy
engine = create_async_engine(
    DATABASE_URL,
    echo=True
)

# Создаём фабрику асинхронных сессий
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Функция-зависимость для FastAPI: создаёт сессию и закрывает её после работы
async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
