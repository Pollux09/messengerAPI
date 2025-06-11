import logging
from collections import defaultdict
import json
from typing import List

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import uvicorn

from models.User import User
from utils.jwtUtil import jwtUtil
from crud import *
from schemas import (
    AccessToken, ChatId, DeleteChat, FindUsersByUsername, LoginData,
    NewMessage, RefreshToken, SendMessage, UserCreate, UserResponse,
    UsersIds, UpdateUserAvatar
)
from utils.mail import email
from database import SessionLocal, engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

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

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, chat_id: str):
        if websocket in self.active_connections[chat_id]:
            logger.warning(f"Попытка повторного подключения WebSocket к чату {chat_id}")
            await websocket.close(code=1000)
            return

        await websocket.accept()
        self.active_connections[chat_id].append(websocket)
        logger.info(f"WebSocket подключен к чату {chat_id}")

    def disconnect(self, websocket: WebSocket, chat_id: str):
        if chat_id in self.active_connections:
            if websocket in self.active_connections[chat_id]:
                self.active_connections[chat_id].remove(websocket)
                logger.info(f"WebSocket отключен от чата {chat_id}")
            if not self.active_connections[chat_id]:
                del self.active_connections[chat_id]

    async def broadcast(self, chat_id: str, message: str):
        if chat_id in self.active_connections:
            logger.info(f"Рассылаем сообщение в чат {chat_id}: {message}")
            for connection in self.active_connections[chat_id]:
                await connection.send_text(message)

manager = ConnectionManager()

class ChatsConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket подключен к пользователю {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            logger.info(f"WebSocket отключен от пользователя {user_id}")
            del self.active_connections[user_id]

    async def broadcast(self, chat: Chat, recipient_user_id: str):
        user_id = str(recipient_user_id)
        data = json.dumps({
            "action": "create",
            "chat": json.loads(chat.json()),
        })
        if self.active_connections.get(user_id):
            logger.info(f"Отправка нового чата пользователю {user_id}")
            await self.active_connections[user_id].send_text(data)

    async def delete_chat(self, user_id: str, chat_id: str):
        data = json.dumps({
            "action": "remove",
            "chat_id": str(chat_id),
        })
        logger.info(f"Удаление чата {chat_id} для пользователя {user_id}")
        if self.active_connections.get(str(user_id)):
            await self.active_connections[str(user_id)].send_text(data)
            
    async def update_last_message(self, chat_id: str, user_id: str, new_message: str):
        data = json.dumps({
            "action": "update_last_message",
            "chat_id": str(chat_id),
            "new_message": new_message,
        })
        logger.info(f"Обновление последнего сообщения чата {chat_id} для пользователя {user_id}")
        if self.active_connections.get(str(user_id)):
            await self.active_connections[str(user_id)].send_text(data)
        

chats_manager = ChatsConnectionManager()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket, chat_id: str = Query(...)):
    await manager.connect(websocket, chat_id)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Получено сообщение в чате {chat_id}: {data}")
            await manager.broadcast(chat_id, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, chat_id)

@app.websocket("/ws/chats")
async def websocket_endpoint(websocket: WebSocket, user_id: str = Query(...)):
    await chats_manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        chats_manager.disconnect(websocket, user_id)

@app.post("/sign-up")
async def sign_up(user: UserCreate, db: Session = Depends(get_db)):
    new_user: User = await create_user(db=db, user=user)
    logger.info(f"Создан пользователь: {new_user.username}")
    return await jwtUtil.createJwtTokens(user=new_user)

@app.post("/get-user-data")
async def get_user_data(request_token: AccessToken, db: Session = Depends(get_db)):
    decoded_access_token = await jwtUtil.decodeJwtToken(token=request_token.access_token)
    if decoded_access_token:
        user_id = decoded_access_token["user_id"]
        if await checkUserExists(db=db, user_id=user_id):
            logger.info(f"Получены данные пользователя {user_id}")
            return await get_user(db=db, user_id=user_id)
    logger.warning("Ошибка при получении данных пользователя")
    raise HTTPException(detail="Unauthorized", status_code=401)

@app.post("/sign-in")
async def login(login_data: LoginData, db: Session = Depends(get_db)):
    user = await login_user(db=db, login_data=login_data)
    if user:
        logger.info(f"Успешный вход пользователя {user.username}")
        return await jwtUtil.createJwtTokens(user=user)
    logger.warning("Неверные данные входа")
    raise HTTPException(detail="login data is invalid", status_code=401)

@app.post("/send-verify-code")
async def send_verify_code(request: Request):
    data = await request.json()
    user_email = data.get("email")
    logger.info(f"Отправка кода подтверждения на {user_email}")
    await email.send_email(user_email)

@app.post("/verify-email-code")
async def verify_email_code(request: Request):
    data = await request.json()
    user_email = data.get("email")
    user_code = data.get("code")
    logger.info(f"Проверка кода {user_code} для email {user_email}")
    return await email.verify_code(user_email=user_email, user_code=user_code)

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

@app.post("/get-chats")
async def get_chats_list(token: AccessToken, db: Session = Depends(get_db)):
    result = await jwtUtil.decodeJwtToken(token=token.access_token)
    if result and result.get("user_id"):
        logger.info(f"Получение списка чатов для пользователя {result['user_id']}")
        return await getChatsList(db=db, user_id=result["user_id"])

@app.post("/search-users")
async def search_users(user: FindUsersByUsername, db: Session = Depends(get_db)):
    logger.info(f"Поиск пользователей по юзернейму: {user.username}")
    return await search_users_by_username(db=db, username=user.username)

@app.post("/send-message")
async def send_message(message: SendMessage, db: Session = Depends(get_db)):
    
    logger.info(f"Отправка сообщения от {message.sender_user_id} к {message.recipient_user_id}")
    # новый чат, при поиске
    if message.chat_id is None:
        data = await create_chat_by_initial_message(db=db, message=message)
        await chats_manager.broadcast(data['chat'], message.recipient_user_id)
        await chats_manager.broadcast(data['chat'], message.sender_user_id)
        return {
            "messages": data["messages"],
            "chat": data["chat"]
        } 
    else:
        # чат уже есть, созданные ранее
        new_message = await add_chat_message(db=db, message=message)
        message_model = NewMessage(
            id=new_message.id,
            chat_id=new_message.chat_id,
            user_id=new_message.user_id,
            text=new_message.text,
            created_at=new_message.created_at,
            message_type=new_message.message_type
        )
        logger.info(f"Новое сообщение в чате {message.chat_id}")
        for connection in manager.active_connections.get(message.chat_id, []):
            await connection.send_text(json.dumps(message_model.json()))
            if new_message.message_type == 'image':
                new_message.text = "Изображение"
            await chats_manager.update_last_message(chat_id=new_message.chat_id, user_id=new_message.user_id, new_message=new_message.text)
            await chats_manager.update_last_message(chat_id=new_message.chat_id, user_id=message.recipient_user_id, new_message=new_message.text)

@app.post("/get-chat-messages-by-usernames")
async def get_chat_messages_by_username(users_ids: UsersIds, db: Session = Depends(get_db)):
    logger.info(f"Поиск чата между пользователями: {users_ids.users_ids}")
    return await find_chat_by_exact_users(db=db, user_ids=users_ids)

@app.post("/load-chat-messages")
async def load_chat_messages(chat_id: ChatId, db: Session = Depends(get_db)):
    logger.info(f"Загрузка сообщений чата {chat_id.chat_id}")
    return await get_chat_messages(db=db, chat_id=chat_id)

@app.post("/update-user-avatar")
async def update_user_avatar(update_user_avatar: UpdateUserAvatar, db: Session = Depends(get_db)):
    logger.info(f"Обновление аватара для пользователя {update_user_avatar.user_id}")
    return await add_user_avatar(db=db, update_avatar=update_user_avatar)

@app.post("/delete-chat")
async def delete_chat(chat_id: DeleteChat, db: Session = Depends(get_db)):
    logger.info(f"Удаление чата {chat_id.chat_id} для пользователя {chat_id.another_user_id}")
    await chats_manager.delete_chat(user_id=chat_id.another_user_id, chat_id=chat_id.chat_id)
    return await delete_chat_by_id(db=db, chat_id=chat_id)

if __name__ == "__main__":
    logger.info("🚀 Запуск сервера FastAPI...")
    uvicorn.run("main:app", reload=True, host="0.0.0.0", port=8000)
 