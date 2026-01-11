from collections import defaultdict
import json
from fastapi import WebSocket


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
            match action_type:
                case "new_message":
                    if message != None:
                        data = {
                            "action": action_type,
                            "message": message,
                        }
                        chat_id = str(chat_id)
                        if chat_id in self.active_connections:
                            for connection in self.active_connections[chat_id]:
                                await connection.send_text(json.dumps(data))
                case "delete_chat":
                    print('WORKING CASE DELETE CHAT')
                    chat_id = str(chat_id)
                    data = {
                        "action": action_type,
                        "chat_id": chat_id,
                    }
                    if chat_id in self.active_connections:
                        for connection in self.active_connections[chat_id]:
                            await connection.send_text(json.dumps(data))
        except Exception as e:
            print('ошибка при send в chat manager send')
            print(e)

                        
chat_manager = ChatManager()