import logging
import uuid
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from crud.users import getUserById
from crud.messages import get_last_chat_message
from crud.crypto_keys import get_user_crypto_keys
from models.Message import Message
from models.Chat import Chat
from schemas.chat import NewMessage, ChatScheme, SendMessage, DeleteChat
from schemas.user import UserResponse


async def get_chats_list(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[ChatScheme]:

    stmt = select(Chat).where(Chat.users_ids.any(user_id))
    result = await session.execute(stmt)
    chats = result.scalars().all()

    chats_list: list[ChatScheme] = []

    for chat in chats:
        # find second user
        another_user_id = next(
            (uid for uid in chat.users_ids if uid != user_id),
            None,
        )
        if not another_user_id:
            continue

        user = await getUserById(session, another_user_id)
        if not user:
            continue

        last_message_raw = await get_last_chat_message(session, chat.id)
        if not last_message_raw:
            continue

        keys = await get_user_crypto_keys(session, user.id)
        if not keys:
            continue

        last_message = NewMessage(
            id=last_message_raw.id,
            chat_id=last_message_raw.chat_id,
            user_id=last_message_raw.user_id,
            text=last_message_raw.text,
            created_at=last_message_raw.created_at,
            message_type=last_message_raw.message_type,
            encrypted_aes_key_sender=last_message_raw.encrypted_aes_key_sender,
            encrypted_aes_key_receiver=last_message_raw.encrypted_aes_key_receiver,
            iv=last_message_raw.iv,
        )

        chats_list.append(
            ChatScheme(
                id=chat.id,
                users_count=chat.users_count,
                type=chat.type,
                users_ids=chat.users_ids,
                another_user=UserResponse(
                    id=user.id,
                    email=user.email,
                    username=user.username,
                    avatar_photo=user.avatar_photo,
                    user_public_key=keys.public_key,
                ),
                last_chat_message=last_message,
            )
        )

    return chats_list


async def find_chat_by_exact_users(
    session: AsyncSession,
    user_ids: list[uuid.UUID],
) -> Chat | None:

    stmt = (
        select(Chat)
        .where(
            Chat.users_ids.op("@>")(user_ids),
            Chat.users_ids.op("<@")(user_ids),
        )
        .options(selectinload(Chat.messages))
    )

    result = await session.execute(stmt)
    return result.scalars().first()


async def create_chat(
    session: AsyncSession,
    message: SendMessage
) -> Chat:

    # check chat exists
    existing_chat = await find_chat_by_exact_users(
        session,
        user_ids=[message.sender_user_id, message.recipient_user_id]
    )
    if existing_chat:
        raise HTTPException(status_code=404, detail="Chat with these users already exists")

    # create chat
    chat = Chat(
        type="private",
        users_ids=[message.sender_user_id, message.recipient_user_id]
    )

    async with session.begin():
        session.add(chat)
        await session.flush()
        await session.refresh(chat)

    return chat


async def create_chat_by_initial_message(
    session: AsyncSession,
    message: SendMessage
) -> dict:
    # check chat exists
    existing_chat = await find_chat_by_exact_users(session, [message.sender_user_id, message.recipient_user_id])
    if existing_chat:
        raise HTTPException(status_code=404, detail="Chat with these users already exists")

    async with session.begin():
        # create chat
        chat = Chat(
            type="private",
            users_ids=[message.sender_user_id, message.recipient_user_id],
        )
        session.add(chat)
        await session.flush()

        # create first message
        created_message = Message(
            chat_id=chat.id,
            user_id=message.sender_user_id,
            text=message.text,
            message_type=message.message_type,
            encrypted_aes_key_receiver=message.encrypted_aes_key_receiver,
            encrypted_aes_key_sender=message.encrypted_aes_key_sender,
            iv=message.iv,
        )
        session.add(created_message)

        await session.flush()
        await session.refresh(chat)
        await session.refresh(created_message)

    # load users data
    another_user_id = next(uid for uid in chat.users_ids if uid != message.sender_user_id)
    current_user_id = message.sender_user_id

    another_user = await getUserById(session, another_user_id)
    current_user = await getUserById(session, current_user_id)

    # get keys
    another_keys = await get_user_crypto_keys(session, another_user.id)
    current_keys = await get_user_crypto_keys(session, current_user.id)

    chat_scheme = ChatScheme(
        id=chat.id,
        users_count=chat.users_count,
        type=chat.type,
        users_ids=chat.users_ids,
        another_user=UserResponse(
            id=another_user.id,
            email=another_user.email,
            username=another_user.username,
            avatar_photo=another_user.avatar_photo,
            user_public_key=another_keys.public_key,
        ),
        last_chat_message=NewMessage(
            id=created_message.id,
            chat_id=created_message.chat_id,
            user_id=created_message.user_id,
            text=created_message.text,
            created_at=created_message.created_at,
            message_type=created_message.message_type,
            encrypted_aes_key_sender=created_message.encrypted_aes_key_sender,
            encrypted_aes_key_receiver=created_message.encrypted_aes_key_receiver,
            iv=created_message.iv,
        )
    )

    return {
        "chat": chat_scheme,
        "messages": [created_message],
        "current_user": UserResponse(
            id=current_user.id,
            email=current_user.email,
            username=current_user.username,
            avatar_photo=current_user.avatar_photo,
            user_public_key=current_keys.public_key,
        )
    }


async def delete_chat_by_id(session: AsyncSession, chat_id: DeleteChat) -> None:
    try:
        stmt = select(Chat).where(Chat.id == chat_id.chat_id)
        result = await session.execute(stmt)
        chat = result.scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        await session.delete(chat)
        await session.flush()
    except Exception as e:
        logging.error('delete chat by id error: ' + str(e))
        raise HTTPException(status_code=500, detail="Failed to delete chat")
