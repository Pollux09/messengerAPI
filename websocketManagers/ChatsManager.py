import json
from fastapi import WebSocket
import logging

from fastapi.encoders import jsonable_encoder

from models.Message import Message
from schemas import NewMessage

logger = logging.getLogger(__name__)

from models.Chat import Chat


class ChatsConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"WebSocket подключен к пользователю {user_id}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            print(f"WebSocket отключен от пользователя {user_id}")
            del self.active_connections[user_id]

    async def send(self, chat: Chat, recipient_user_id: str):
        user_id = str(recipient_user_id)
        data = json.dumps({
            "action": "create",
            "chat": json.loads(chat.json()),
        })
        if self.active_connections.get(user_id):
            await self.active_connections[user_id].send_text(data)

    async def delete_chat(self, user_id: str, chat_id: str):
        data = json.dumps({
            "action": "remove",
            "chat_id": str(chat_id),
        })
        if self.active_connections.get(str(user_id)):
            await self.active_connections[str(user_id)].send_text(data)
            
    async def update_last_message(self, chat_id: str, user_id: str, new_message: NewMessage):
        try:
            data = json.dumps(jsonable_encoder({
                "action": "update_last_message",
                "chat_id": str(chat_id),
                "new_message": new_message,
            }))
            if self.active_connections.get(str(user_id)):
                await self.active_connections[str(user_id)].send_text(data)
        except Exception as e:
            print('ошибка при отправке сообщения по веб сокету')
            print(e)
        

chats_manager = ChatsConnectionManager()