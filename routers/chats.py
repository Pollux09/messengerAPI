import uuid
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.encoders import jsonable_encoder
from config.db import session_helper
from config.logger import logger
from crud.chats import (
    add_group_members,
    build_chat_scheme,
    create_chat_by_initial_message,
    create_group_chat,
    delete_chat_by_id,
    ensure_chat_member,
    get_chat_by_id,
    get_chat_messages_by_users,
    get_chats_list,
    remove_group_member,
    serialize_message,
    update_group_avatar,
    update_group_title,
)
from crud.messages import get_chat_messages, add_chat_message
from crud.users import ensure_user_is_approved, get_user_by_id, update_user_last_seen
from dependencies.deps import SessionDep, UserTokenDep
from schemas.chat import (
    ChatScheme,
    ChatId,
    CreateGroupChat,
    DeleteChat,
    GroupMemberRemove,
    GroupMembersUpdate,
    NewMessage,
    SendMessage,
    UpdateChatAvatar,
    UpdateGroupTitle,
)
from schemas.user import UsersIds
from websocket_managers.chats_manager import chats_manager
from websocket_managers.chat_manager import chat_manager
from utils.jwt_util import jwt_util

router = APIRouter(prefix="/chats", tags=["chats"])

async def _get_websocket_user(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return None

    try:
        decoded = await jwt_util.decode_jwt_token(token=token, required_type="access")
    except HTTPException as exc:
        await websocket.close(code=4401, reason=str(exc.detail))
        return None

    async with session_helper.session_factory() as session:
        try:
            user = await get_user_by_id(session=session, user_id=decoded["user_id"])
            return await ensure_user_is_approved(user)
        except HTTPException as exc:
            await websocket.close(code=4403, reason=str(exc.detail))
            return None


@router.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket, chat_id: str):
    user = await _get_websocket_user(websocket)
    if user is None:
        return

    async with session_helper.session_factory() as session:
        try:
            chat = await get_chat_by_id(session, uuid.UUID(chat_id))
            await ensure_chat_member(chat, user.id)
        except ValueError:
            await websocket.close(code=4400, reason="Invalid chat ID")
            return
        except HTTPException as exc:
            await websocket.close(code=4403, reason=str(exc.detail))
            return

    await chat_manager.connect(websocket, chat_id)
    try:
        while True:
            data = await websocket.receive_text()
            if json.loads(data)['type'] != 'ping':
                await chat_manager.send(chat_id=chat_id, message=data, action_type="new_message")
    except WebSocketDisconnect:
        chat_manager.disconnect(websocket, chat_id)
    except Exception as exc:
        chat_manager.disconnect(websocket, chat_id)
        logger.warning("Chat websocket error for %s: %s", str(user.id), str(exc))
    finally:
        async with session_helper.session_factory() as session:
            try:
                await update_user_last_seen(session, user.id)
            except Exception as exc:
                logger.warning("Failed to update last_seen for %s: %s", str(user.id), str(exc))


@router.websocket("/ws/chats")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    user = await _get_websocket_user(websocket)
    if user is None:
        return

    if str(user.id) != user_id:
        await websocket.close(code=4403, reason="User mismatch")
        return

    await chats_manager.connect(websocket, user_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        chats_manager.disconnect(user_id)
    finally:
        async with session_helper.session_factory() as session:
            try:
                await update_user_last_seen(session, user.id)
            except Exception as exc:
                logger.warning("Failed to update last_seen for %s: %s", str(user.id), str(exc))


@router.post("/get-chats")
async def get_chats(session: SessionDep, decoded_access_token: UserTokenDep):
    return await get_chats_list(session=session, user_id=decoded_access_token["user_id"])


@router.post("/get-chat-messages-by-usernames")
async def get_chat_messages_by_username(
    data: UsersIds,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
):
    return await get_chat_messages_by_users(
        session=session,
        current_user_id=decoded_access_token["user_id"],
        user_ids=data.users_ids,
    )


@router.post("/load-chat-messages")
async def load_chat_messages(chat_id: ChatId, session: SessionDep, decoded_access_token: UserTokenDep):
    chat = await get_chat_by_id(session, chat_id.chat_id)
    if decoded_access_token["user_id"] not in chat.users_ids:
        raise HTTPException(status_code=403, detail="You are not a member of this chat")
    return await get_chat_messages(session=session, chat_id=chat_id)


@router.post("/get-chat", response_model=ChatScheme)
async def get_chat(
    chat_id: ChatId,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
):
    chat = await get_chat_by_id(session, chat_id.chat_id)
    await ensure_chat_member(chat, decoded_access_token["user_id"])
    return await build_chat_scheme(session, chat, decoded_access_token["user_id"])


@router.post("/delete-chat")
async def delete_chat(
    chat_id: DeleteChat,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
) -> dict[str, bool | str]:
    try:
        deleted_chat = await delete_chat_by_id(
            session=session,
            current_user_id=decoded_access_token["user_id"],
            chat_id=chat_id,
        )

        await chat_manager.send(chat_id=chat_id.chat_id, action_type="delete_chat")
        for participant_id in deleted_chat.users_ids:
            await chats_manager.delete_chat(user_id=participant_id, chat_id=chat_id.chat_id)

        await session.commit()
        return {'status': True, 'action': 'delete chat'}
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.error('Delete chat error: ' + str(e))
        raise HTTPException(status_code=500, detail="Failed to delete chat")


@router.post("/send-message")
async def send_message(
    message: SendMessage,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
):
    try:
        if decoded_access_token["user_id"] != message.sender_user_id:
            raise HTTPException(status_code=403, detail="Sender mismatch")

        # new chat by search
        if message.chat_id is None:
            data = await create_chat_by_initial_message(session=session, message=message)
            for participant_id in data["chat"].users_ids:
                await chats_manager.send(data['chat'], participant_id, action="create")
            return {
                "messages": data["messages"],
                "chat": data["chat"]
            }
        else:
            # already has chat
            chat = await get_chat_by_id(session, uuid.UUID(message.chat_id))
            await ensure_chat_member(chat, message.sender_user_id)
            new_message = await add_chat_message(session=session, message=message)
            await session.commit()
            
            message_model = NewMessage(
                id=new_message.id,
                chat_id=new_message.chat_id,
                user_id=new_message.user_id,
                text=new_message.text,
                created_at=new_message.created_at,
                message_type=new_message.message_type,
                encrypted_aes_key_receiver=new_message.encrypted_aes_key_receiver,
                encrypted_aes_key_sender=new_message.encrypted_aes_key_sender,
                encrypted_keys=new_message.encrypted_keys or {},
                iv=new_message.iv,
            )
            await chat_manager.send(
                chat_id=new_message.chat_id,
                action_type="new_message",
                message=jsonable_encoder(message_model),
            )
            chat = await get_chat_by_id(session, new_message.chat_id)
            for participant_id in chat.users_ids:
                await chats_manager.update_last_message(
                    chat_id=new_message.chat_id,
                    user_id=participant_id,
                    new_message=message_model,
                )
            return {
                "messages": [serialize_message(new_message)],
                "chat": await build_chat_scheme(session, chat, message.sender_user_id),
            }
    except HTTPException:
        await session.rollback()
        raise
    except Exception as e:
        await session.rollback()
        logger.exception('Send message error: %s', str(e))
        raise HTTPException(status_code=500, detail="Failed to send message")


@router.post("/create-group-chat")
async def create_group_chat_handler(
    data: CreateGroupChat,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
):
    chat = await create_group_chat(session, decoded_access_token["user_id"], data)
    for participant_id in chat.users_ids:
        await chats_manager.send(chat, participant_id, action="create")
    return chat


@router.post("/update-group-title")
async def update_group_title_handler(
    data: UpdateGroupTitle,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
):
    chat = await update_group_title(session, decoded_access_token["user_id"], data)
    for participant_id in chat.users_ids:
        await chats_manager.send(chat, participant_id, action="update")
    return chat


@router.post("/add-group-members")
async def add_group_members_handler(
    data: GroupMembersUpdate,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
):
    previous_chat = await get_chat_by_id(session, data.chat_id)
    previous_member_ids = {str(user_id) for user_id in previous_chat.users_ids}
    chat = await add_group_members(session, decoded_access_token["user_id"], data)
    for participant_id in chat.users_ids:
        action = "create" if str(participant_id) not in previous_member_ids else "update"
        await chats_manager.send(chat, participant_id, action=action)
    return chat


@router.post("/remove-group-member")
async def remove_group_member_handler(
    data: GroupMemberRemove,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
):
    previous_chat = await get_chat_by_id(session, data.chat_id)
    previous_member_ids = {str(user_id) for user_id in previous_chat.users_ids}
    chat = await remove_group_member(session, decoded_access_token["user_id"], data)
    current_member_ids = {str(user_id) for user_id in chat.users_ids}
    for participant_id in chat.users_ids:
        await chats_manager.send(chat, participant_id, action="update")
    for removed_member_id in previous_member_ids - current_member_ids:
        await chats_manager.delete_chat(user_id=removed_member_id, chat_id=str(chat.id))
    return chat


@router.post("/update-group-avatar")
async def update_group_avatar_handler(
    data: UpdateChatAvatar,
    session: SessionDep,
    decoded_access_token: UserTokenDep,
):
    chat = await update_group_avatar(
        session,
        decoded_access_token["user_id"],
        data.chat_id,
        data.photo_data,
    )
    for participant_id in chat.users_ids:
        await chats_manager.send(chat, participant_id, action="update")
    return chat
