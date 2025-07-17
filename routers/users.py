from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from crud.users import search_users_by_username, checkUserExists, get_user, add_user_avatar
from schemas import FindUsersByUsername, UpdateUserAvatar
from database import get_db
import logging
from utils.jwtUtil import verify_user_middleware

logger = logging.getLogger(__name__)

usersRouter = APIRouter()


@usersRouter.post("/search-users")
async def search_users(user: FindUsersByUsername, db: Session = Depends(get_db)):
    logger.info(f"Поиск пользователей по юзернейму: {user.username}")
    return await search_users_by_username(db=db, username=user.username)

@usersRouter.post("/get-user-data")
async def get_user_data(db: Session = Depends(get_db), decoded_access_token = Depends(verify_user_middleware)):
    if decoded_access_token:
        user_id = decoded_access_token["user_id"]
        if await checkUserExists(db=db, user_id=user_id):
            logger.info(f"Получены данные пользователя {user_id}")
            return await get_user(db=db, user_id=user_id)
    logger.warning("Ошибка при получении данных пользователя")
    raise HTTPException(detail="Unauthorized", status_code=401)

@usersRouter.post("/update-user-avatar")
async def update_user_avatar(update_user_avatar: UpdateUserAvatar, db: Session = Depends(get_db)):
    logger.info(f"Обновление аватара для пользователя {update_user_avatar.user_id}")
    return await add_user_avatar(db=db, update_avatar=update_user_avatar)