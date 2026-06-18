from collections import defaultdict
import json
from fastapi import WebSocket
from config.logger import logger


class ChatManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, chat_id: str):
        if websocket in self.active_connections[chat_id]:
            await websocket.close(code=1000)
            return

        await websocket.accept()
        self.active_connections[chat_id].append(websocket)

    def disconnect(self, websocket: WebSocket, chat_id: str):
        if chat_id in self.active_connections:
            if websocket in self.active_connections[chat_id]:
                self.active_connections[chat_id].remove(websocket)
            if not self.active_connections[chat_id]:
                del self.active_connections[chat_id]

    async def send(self, chat_id: str, action_type: str, message = None):
        try:
            chat_id = str(chat_id)
            match action_type:
                case "new_message":
                    if message is not None:
                        data = {
                            "action": action_type,
                            "message": message,
                        }
                        if chat_id in self.active_connections:
                            stale_connections = []
                            for connection in list(self.active_connections[chat_id]):
                                try:
                                    await connection.send_text(json.dumps(data))
                                except Exception:
                                    stale_connections.append(connection)
                            for connection in stale_connections:
                                self.disconnect(connection, chat_id)
                case "delete_chat":
                    data = {
                        "action": action_type,
                        "chat_id": chat_id,
                    }
                    if chat_id in self.active_connections:
                        stale_connections = []
                        for connection in list(self.active_connections[chat_id]):
                            try:
                                await connection.send_text(json.dumps(data))
                            except Exception:
                                stale_connections.append(connection)
                        for connection in stale_connections:
                            self.disconnect(connection, chat_id)
        except Exception as e:
            logger.error("Chat websocket send error: %s", str(e))

                        
chat_manager = ChatManager()
