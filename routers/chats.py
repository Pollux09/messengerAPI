import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from config.logger import logger
from crud.chats import find_chat_by_exact_users, delete_chat_by_id, create_chat_by_initial_message, get_chats_list
from crud.messages import get_chat_messages, add_chat_message
from dependencies.deps import SessionDep, UserTokenDep
from schemas.chat import ChatId, NewMessage, SendMessage, DeleteChat
from schemas.user import UsersIds, UserId
from websocket_managers.chats_manager import chats_manager
from websocket_managers.chat_manager import chat_manager

router = APIRouter(prefix="/chats", tags=["chats"])


@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket, chat_id: ChatId):
    await chat_manager.connect(websocket, chat_id)
    try:
        while True:
            data = await websocket.receive_text()
            if json.loads(data)['type'] != 'ping':
                await chat_manager.send(chat_id=chat_id, message=data, action_type="new_message")
    except WebSocketDisconnect:
        chat_manager.disconnect(websocket, chat_id)


@router.websocket("/ws/chats")
async def websocket_endpoint(websocket: WebSocket, user_id: UserId):
    await chats_manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        chats_manager.disconnect(websocket, user_id)


@router.post("/get-chats")
async def get_chats(session: SessionDep, decoded_access_token: UserTokenDep):
    return await get_chats_list(session=session, user_id=decoded_access_token["user_id"])


@router.post("/get-chat-messages-by-usernames")
async def get_chat_messages_by_username(data: UsersIds, session: SessionDep):
    return await find_chat_by_exact_users(session=session, user_ids=data.users_ids)


@router.post("/load-chat-messages")
async def load_chat_messages(chat_id: ChatId, session: SessionDep):
    return await get_chat_messages(session=session, chat_id=chat_id)


@router.post("/delete-chat")
async def delete_chat(chat_id: DeleteChat, session: SessionDep) -> dict[str, bool | str]:
    try:
        await delete_chat_by_id(session=session, chat_id=chat_id)

        await chat_manager.send(chat_id=chat_id.chat_id, action_type="delete_chat")
        await chats_manager.delete_chat(user_id=chat_id.another_user_id, chat_id=chat_id.chat_id)

        await session.commit()
        return {'status': True, 'action': 'delete chat'}
    except Exception as e:
        await session.rollback()
        logger.error('Delete chat error: ' + str(e))
        raise HTTPException(status_code=500, detail="Failed to delete chat")


@router.post("/send-message")
async def send_message(message: SendMessage, session: SessionDep):
    try:
        # new chat by search
        if message.chat_id is None:
            data = await create_chat_by_initial_message(session=session, message=message)
            await chats_manager.send(data['chat'], message.recipient_user_id)
            await chats_manager.send(data['chat'], message.sender_user_id)
            return {
                "messages": data["messages"],
                "chat": data["chat"]
            }
        else:
            # already has chat
            new_message = await add_chat_message(session=session, message=message)
            
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
            await chat_manager.send(chat_id=new_message.chat_id, action_type="new_message", message=json.dumps(message_model.json()))
            if new_message.message_type == 'image':
                    new_message.text = "Изображение"

            await chats_manager.update_last_message(chat_id=new_message.chat_id, user_id=new_message.user_id, new_message=message_model)
            await chats_manager.update_last_message(chat_id=new_message.chat_id, user_id=message.recipient_user_id, new_message=message_model)
    except Exception as e:
        logger.error('Send message error: ' + str(e))
        raise HTTPException(status_code=500, detail="Failed to send message")
