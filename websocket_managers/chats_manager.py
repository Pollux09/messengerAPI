import json
from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder
from config.logger import logger
from models.chat import Chat
from schemas.chat import NewMessage


class ChatsConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    def is_online(self, user_id: str) -> bool:
        return str(user_id) in self.active_connections

    async def send(self, chat: Chat, recipient_user_id: str, action: str = "create"):
        user_id = str(recipient_user_id)
        data = json.dumps({
            "action": action,
            "chat": json.loads(chat.json()),
        })
        if self.active_connections.get(user_id):
            try:
                await self.active_connections[user_id].send_text(data)
            except Exception as e:
                logger.warning("Failed to push chat update to %s: %s", user_id, str(e))
                self.disconnect(user_id)

    async def delete_chat(self, user_id: str, chat_id: str):
        data = json.dumps({
            "action": "remove",
            "chat_id": str(chat_id),
        })
        if self.active_connections.get(str(user_id)):
            try:
                await self.active_connections[str(user_id)].send_text(data)
            except Exception as e:
                logger.warning("Failed to push chat removal to %s: %s", str(user_id), str(e))
                self.disconnect(str(user_id))
            
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
            logger.warning("Failed to update last message for %s: %s", str(user_id), str(e))
            self.disconnect(str(user_id))


chats_manager = ChatsConnectionManager()
