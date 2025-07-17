import json
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from crud.chats import getChatsList, find_chat_by_exact_users, delete_chat_by_id, create_chat_by_initial_message
from crud.messages import get_chat_messages, add_chat_message
from database import get_db
from schemas import ChatId, DeleteChat, NewMessage, SendMessage, UsersIds
from utils.jwtUtil import verify_user_middleware
from sqlalchemy.orm import Session
from websocketManagers.ChatsManager import chats_manager
from websocketManagers.ChatManager import chat_manager
import logging

logger = logging.getLogger(__name__)
 
chatsRouter = APIRouter()

@chatsRouter.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket, chat_id: str = Query(...)):
    await chat_manager.connect(websocket, chat_id)
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Получено сообщение в чате {chat_id}: {data}")
            if json.loads(data)['type'] != 'ping':
                await chat_manager.send(chat_id=chat_id, message=data, action_type="new_message")
    except WebSocketDisconnect:
        chat_manager.disconnect(websocket, chat_id)

@chatsRouter.websocket("/ws/chats")
async def websocket_endpoint(websocket: WebSocket, user_id: str = Query(...)):
    await chats_manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        chats_manager.disconnect(websocket, user_id)

@chatsRouter.post("/get-chats")
async def get_chats_list(db: Session = Depends(get_db), decoded_access_token = Depends(verify_user_middleware)):
    logger.info(f"Получение списка чатов для пользователя {decoded_access_token['user_id']}")
    return await getChatsList(db=db, user_id=decoded_access_token["user_id"])
    
@chatsRouter.post("/get-chat-messages-by-usernames")
async def get_chat_messages_by_username(users_ids: UsersIds, db: Session = Depends(get_db)):
    logger.info(f"Поиск чата между пользователями: {users_ids.users_ids}")
    return await find_chat_by_exact_users(db=db, user_ids=users_ids)

@chatsRouter.post("/load-chat-messages")
async def load_chat_messages(chat_id: ChatId, db: Session = Depends(get_db)):
    logger.info(f"Загрузка сообщений чата {chat_id.chat_id}")
    return await get_chat_messages(db=db, chat_id=chat_id)

@chatsRouter.post("/delete-chat")
async def delete_chat(chat_id: DeleteChat, db: Session = Depends(get_db)):
    logger.info(f"Удаление чата {chat_id.chat_id} для пользователя {chat_id.another_user_id}")
    await chat_manager.send(chat_id=chat_id.chat_id, action_type="delete_chat")
    await chats_manager.delete_chat(user_id=chat_id.another_user_id, chat_id=chat_id.chat_id)
    
    return await delete_chat_by_id(db=db, chat_id=chat_id)


@chatsRouter.post("/send-message")
async def send_message(message: SendMessage, db: Session = Depends(get_db)):
    print('запрос на отправку сообщения получен')
    try:
        logger.info(f"Отправка сообщения от {message.sender_user_id} к {message.recipient_user_id}")
        # новый чат, при поиске
        if message.chat_id is None:
            print('chat_id равен None')
            data = await create_chat_by_initial_message(db=db, message=message)
            await chats_manager.send(data['chat'], message.recipient_user_id)
            await chats_manager.send(data['chat'], message.sender_user_id)
            return {
                "messages": data["messages"],
                "chat": data["chat"]
            }
        else:
            # чат уже есть, созданный ранее
            new_message = await add_chat_message(db=db, message=message)
            
            message_model = NewMessage(
                id=new_message.id,
                chat_id=new_message.chat_id,
                user_id=new_message.user_id,
                text=new_message.text,
                created_at=new_message.created_at,
                message_type=new_message.message_type,
                encrypted_aes_key_receiver=new_message.encrypted_aes_key_receiver,
                encrypted_aes_key_sender=new_message.encrypted_aes_key_sender,
                iv=new_message.iv,
            )
            print('новое сообщение в чате')
            await chat_manager.send(chat_id=new_message.chat_id, action_type="new_message", message=json.dumps(message_model.json()))
            if new_message.message_type == 'image':
                    new_message.text = "Изображение"
                    
            print('должно отправиться новое сообщение через веб сокет')
            await chats_manager.update_last_message(chat_id=new_message.chat_id, user_id=new_message.user_id, new_message=message_model)
            await chats_manager.update_last_message(chat_id=new_message.chat_id, user_id=message.recipient_user_id, new_message=message_model)
    except Exception as e:
        print("ERROR IS")
        print(e)
        return e
        