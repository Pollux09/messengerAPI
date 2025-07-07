from asyncio import get_event_loop
import logging
import time
from fastapi import Depends, FastAPI, HTTPException, Request
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn

from models.User import User
from utils.jwtUtil import jwtUtil
from crud import *
from schemas import (
    EmailScheme, LoginData, LoginSuccessResponse, RefreshToken, UserCreate, VerifyEmailScheme
)
from utils.mail import email
from database import SessionLocal
from alembic.config import Config
from alembic import command
import os
from routers.chats import chatsRouter
from routers.users import usersRouter
from routers.secure import secureRouter

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
app = FastAPI()

app.include_router(chatsRouter)
app.include_router(usersRouter)
app.include_router(secureRouter)

async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)    

async def run_migrations_async():
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", os.getenv("POSTGRES_URL").replace("postgres://", "postgresql+psycopg2://"))
    command.upgrade(alembic_cfg, "head")

def run_migrations():
    loop = get_event_loop()
    loop.run_until_complete(run_migrations_async())

@app.post("/sign-up")
async def sign_up(user: UserCreate, db: Session = Depends(get_db)):
    new_user: User = await create_user(db=db, user=user)
    logger.info(f"Создан пользователь: {new_user.username}")
    return await jwtUtil.createJwtTokens(user=new_user)

@app.post("/sign-in")
async def login(login_data: LoginData, db: Session = Depends(get_db)):
    user = await login_user(db=db, login_data=login_data)
    if user:
        logger.info(f"Успешный вход пользователя {user.username}")
        tokens = await jwtUtil.createJwtTokens(user=user)
        crypt_keys = await get_user_crypto_keys(db=db, user_id=user.id)
        
        return LoginSuccessResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            crypt_keys=UploadCryptKeys(
                public_key=crypt_keys.public_key,
                private_key=crypt_keys.private_key,
            )
        )
    logger.warning("Неверные данные входа")
    raise HTTPException(detail="login data is invalid", status_code=401)

from fastapi import HTTPException

@app.post("/send-verify-code")
async def send_verify_code(data: EmailScheme, db: Session = Depends(get_db)):
    try:
        user = await check_user_exists(db=db, email=data.email)
        if user:
            raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

        print(f"Отправка кода подтверждения на {data.email}")
        await email.send_email(data.email)
    except HTTPException:
        raise
    except Exception as e:
        print('произошла какая-то ошибка')
        print(e)
        raise HTTPException(status_code=500, detail="Ошибка сервера при отправке письма")


@app.post("/verify-email-code")
async def verify_email_code(verify: VerifyEmailScheme):
    print(f"Проверка кода {verify.code} для email {verify.email}")
    return await email.verify_code(user_email=verify.email, user_code=verify.code)

@app.post("/refresh-tokens")
async def refresh_tokens(token: RefreshToken, db: Session = Depends(get_db)):
    decoded = await jwtUtil.decodeJwtToken(token=token.refresh_token)
    if decoded:
        user_id = decoded["user_id"]
        if await checkUserExists(db=db, user_id=user_id):
            logger.info(f"Обновление токенов для пользователя {user_id}")
            user = await get_user(db=db, user_id=user_id)
            return await jwtUtil.createJwtTokens(user=user)
    logger.warning("Ошибка при обновлении токенов")
    raise HTTPException(status_code=401, detail="Invalid refresh token")

import asyncio

async def run_migrations_on_startup():
    logger.info("🚀 Running migrations...")
    alembic_cfg = Config("alembic.ini")
    db_url = os.getenv("POSTGRES_URL").replace("postgres://", "postgresql+psycopg2://")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    
    # Запускаем миграции в отдельном потоке
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, command.upgrade, alembic_cfg, "head")

# Вызываем миграции при старте приложения
@app.on_event("startup")
async def startup_event():
    print('application is starting...')
    await run_migrations_on_startup()
 