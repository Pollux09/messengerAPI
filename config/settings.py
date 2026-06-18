from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # App
    APP_NAME: str = "Pinq"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_RELOAD: bool = True


    ENVIRONMENT: str = "development"

    # JWT
    JWT_ALGORITHM: str = "HS256"
    JWT_SECRET_TOKEN: str

    # Database
    DATABASE_URL: PostgresDsn

    # PostgreSQL connection details
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    # SQLAlchemy
    ECHO: bool = True
    ECHO_POOL: bool = True
    POOL_SIZE: int = 10
    MAX_OVERFLOW: int = 10

    # cache
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # SMTP
    SMTP_SERVER: str
    SMTP_PORT: int
    SMTP_USERNAME: str
    SMTP_PASSWORD: str
    SMTP_FROM: str = "no-reply@messenger.local"
    SMTP_USE_TLS: bool = True

    # Default admin bootstrap
    ADMIN_EMAIL: str = "admin@messenger.local"
    ADMIN_PASSWORD: str = "Admin12345!"
    ADMIN_USERNAME: str = "@admin"

    # Default test user bootstrap
    TEST_USER_EMAIL: str = "test@messenger.local"
    TEST_USER_PASSWORD: str = "Test12345!"
    TEST_USER_USERNAME: str = "@testuser"

settings = Settings() # type: ignore
