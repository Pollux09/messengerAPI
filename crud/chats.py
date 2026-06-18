import uuid
from fastapi import HTTPException
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from crud.crypto_keys import get_user_crypto_keys
from crud.messages import add_chat_message, get_last_chat_message
from crud.users import build_user_response, get_user_by_id
from models.chat import Chat
from models.chat_member import ChatMember
from models.message import Message
from schemas.chat import (
    ChatId,
    ChatScheme,
    CreateGroupChat,
    DeleteChat,
    GroupMemberRemove,
    GroupMembersUpdate,
    NewMessage,
    SendMessage,
    UpdateGroupTitle,
)
from schemas.user import UserResponse


def serialize_message(message: Message) -> NewMessage:
    return NewMessage(
        id=message.id,
        chat_id=message.chat_id,
        user_id=message.user_id,
        text=message.text,
        created_at=message.created_at,
        message_type=message.message_type,
        encrypted_aes_key_sender=message.encrypted_aes_key_sender,
        encrypted_aes_key_receiver=message.encrypted_aes_key_receiver,
        encrypted_keys=message.encrypted_keys or {},
        iv=message.iv,
    )


async def ensure_chat_member(chat: Chat, user_id: uuid.UUID) -> None:
    if user_id not in chat.users_ids:
        raise HTTPException(status_code=403, detail="You are not a member of this chat")


async def get_chat_by_id(session: AsyncSession, chat_id: uuid.UUID) -> Chat:
    result = await session.execute(
        select(Chat)
        .options(selectinload(Chat.members))
        .where(Chat.id == chat_id)
    )
    chat = result.scalars().first()
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


async def build_chat_scheme(session: AsyncSession, chat: Chat, current_user_id: uuid.UUID) -> ChatScheme:
    participants: list[UserResponse] = []
    another_user: UserResponse | None = None

    for participant_id in chat.users_ids:
        user = await get_user_by_id(session, participant_id)
        user_response = await build_user_response(session, user)
        participants.append(user_response)
        if participant_id != current_user_id and chat.type == "private":
            another_user = user_response

    last_message_raw = await get_last_chat_message(session, chat.id)
    last_message = serialize_message(last_message_raw) if last_message_raw else None

    return ChatScheme(
        id=chat.id,
        users_count=chat.users_count,
        type=chat.type,
        users_ids=chat.users_ids,
        title=chat.title,
        avatar_photo=chat.avatar_photo,
        created_by=chat.created_by,
        participants=participants,
        another_user=another_user,
        last_chat_message=last_message,
        can_manage=chat.type == "group" and chat.created_by == current_user_id,
    )


async def get_chats_list(session: AsyncSession, user_id: uuid.UUID) -> list[ChatScheme]:
    stmt = (
        select(Chat)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .options(selectinload(Chat.members))
        .where(ChatMember.user_id == user_id)
    )
    result = await session.execute(stmt)
    chats = result.scalars().all()
    chats_list = [await build_chat_scheme(session, chat, user_id) for chat in chats]
    chats_list.sort(
        key=lambda item: (
            item.last_chat_message.created_at.timestamp()
            if item.last_chat_message
            else 0
        ),
        reverse=True,
    )
    return chats_list


async def find_chat_by_exact_users(session: AsyncSession, user_ids: list[uuid.UUID]) -> Chat | None:
    total_members_subquery = (
        select(
            ChatMember.chat_id.label("chat_id"),
            func.count(ChatMember.user_id).label("member_count"),
        )
        .group_by(ChatMember.chat_id)
        .subquery()
    )
    stmt = (
        select(Chat)
        .join(total_members_subquery, total_members_subquery.c.chat_id == Chat.id)
        .join(ChatMember, ChatMember.chat_id == Chat.id)
        .options(selectinload(Chat.members))
        .where(
            Chat.type == "private",
            total_members_subquery.c.member_count == len(user_ids),
            ChatMember.user_id.in_(user_ids),
        )
        .group_by(Chat.id, total_members_subquery.c.member_count)
        .having(func.count(distinct(ChatMember.user_id)) == len(user_ids))
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def get_chat_messages_by_users(
    session: AsyncSession,
    current_user_id: uuid.UUID,
    user_ids: list[uuid.UUID],
) -> dict | None:
    all_user_ids = list({*user_ids, current_user_id})
    if len(all_user_ids) != 2:
        raise HTTPException(status_code=400, detail="Private chat must contain exactly two users")

    chat = await find_chat_by_exact_users(session, all_user_ids)
    if chat is None:
        return None

    messages_result = await session.execute(
        select(Message).where(Message.chat_id == chat.id).order_by(Message.created_at.asc())
    )
    messages = messages_result.scalars().all()
    return {
        "chat": await build_chat_scheme(session, chat, current_user_id),
        "messages": [serialize_message(message) for message in messages],
    }


async def create_chat_by_initial_message(session: AsyncSession, message: SendMessage) -> dict:
    if message.recipient_user_id is None:
        raise HTTPException(status_code=400, detail="recipient_user_id is required for private chat")
    if message.recipient_user_id == message.sender_user_id:
        raise HTTPException(status_code=400, detail="You cannot create a chat with yourself")

    await get_user_by_id(session, message.sender_user_id)
    await get_user_by_id(session, message.recipient_user_id)

    user_ids = [message.sender_user_id, message.recipient_user_id]
    existing_chat = await find_chat_by_exact_users(session, user_ids)
    if existing_chat:
        message.chat_id = str(existing_chat.id)
        created_message = await add_chat_message(session, message)
        await session.commit()
        await session.refresh(existing_chat)
        return {
            "chat": await build_chat_scheme(session, existing_chat, message.sender_user_id),
            "messages": [serialize_message(created_message)],
        }

    chat = Chat(
        type="private",
        users_ids=user_ids,
        created_by=message.sender_user_id,
    )
    session.add(chat)
    await session.flush()

    message.chat_id = str(chat.id)
    created_message = await add_chat_message(session, message)
    await session.commit()
    await session.refresh(chat)

    return {
        "chat": await build_chat_scheme(session, chat, message.sender_user_id),
        "messages": [serialize_message(created_message)],
    }


async def create_group_chat(session: AsyncSession, current_user_id: uuid.UUID, data: CreateGroupChat) -> ChatScheme:
    title = data.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Group title cannot be empty")

    users_ids = {current_user_id}

    for user_id in data.user_ids:
        await get_user_by_id(session, user_id)
        users_ids.add(user_id)

    if len(users_ids) < 2:
        raise HTTPException(status_code=400, detail="Group chat must contain at least two members")

    chat = Chat(
        type="group",
        title=title,
        created_by=current_user_id,
        users_ids=list(users_ids),
    )
    session.add(chat)
    await session.flush()
    await session.commit()
    await session.refresh(chat)

    return await build_chat_scheme(session, chat, current_user_id)


async def update_group_title(session: AsyncSession, current_user_id: uuid.UUID, data: UpdateGroupTitle) -> ChatScheme:
    chat = await get_chat_by_id(session, data.chat_id)
    if chat.type != "group":
        raise HTTPException(status_code=400, detail="Only group chats can be renamed")
    if chat.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="Only group creator can rename this chat")
    await ensure_chat_member(chat, current_user_id)

    title = data.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Group title cannot be empty")

    chat.title = title
    await session.commit()
    await session.refresh(chat)
    return await build_chat_scheme(session, chat, current_user_id)


async def add_group_members(session: AsyncSession, current_user_id: uuid.UUID, data: GroupMembersUpdate) -> ChatScheme:
    chat = await get_chat_by_id(session, data.chat_id)
    if chat.type != "group":
        raise HTTPException(status_code=400, detail="Only group chats support members management")
    if chat.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="Only group creator can add members")
    await ensure_chat_member(chat, current_user_id)

    users_ids = set(chat.users_ids)
    for user_id in data.user_ids:
        await get_user_by_id(session, user_id)
        users_ids.add(user_id)

    chat.users_ids = list(users_ids)
    await session.commit()
    chat = await get_chat_by_id(session, chat.id)
    return await build_chat_scheme(session, chat, current_user_id)


async def remove_group_member(session: AsyncSession, current_user_id: uuid.UUID, data: GroupMemberRemove) -> ChatScheme:
    chat = await get_chat_by_id(session, data.chat_id)
    if chat.type != "group":
        raise HTTPException(status_code=400, detail="Only group chats support members management")
    if chat.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="Only group creator can remove members")
    await ensure_chat_member(chat, current_user_id)

    user = await get_user_by_id(session, data.user_id)
    if user.id == chat.created_by:
        raise HTTPException(status_code=400, detail="Group creator cannot be removed")
    if user.id not in chat.users_ids:
        raise HTTPException(status_code=404, detail="User is not a member of this group")

    users_ids = [member_id for member_id in chat.users_ids if member_id != user.id]
    if len(users_ids) < 2:
        raise HTTPException(status_code=400, detail="Group chat must contain at least two members")

    chat.users_ids = users_ids
    await session.commit()
    chat = await get_chat_by_id(session, chat.id)
    return await build_chat_scheme(session, chat, current_user_id)


async def update_group_avatar(session: AsyncSession, current_user_id: uuid.UUID, chat_id: uuid.UUID, photo_data: str) -> ChatScheme:
    chat = await get_chat_by_id(session, chat_id)
    if chat.type != "group":
        raise HTTPException(status_code=400, detail="Only group chats can have avatar")
    if chat.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="Only group creator can update avatar")
    await ensure_chat_member(chat, current_user_id)
    if not photo_data:
        raise HTTPException(status_code=400, detail="Photo data cannot be empty")

    chat.avatar_photo = photo_data
    await session.commit()
    await session.refresh(chat)
    return await build_chat_scheme(session, chat, current_user_id)


async def delete_chat_by_id(session: AsyncSession, current_user_id: uuid.UUID, chat_id: DeleteChat) -> Chat:
    chat = await get_chat_by_id(session, chat_id.chat_id)
    await ensure_chat_member(chat, current_user_id)
    if chat.type == "group" and chat.created_by != current_user_id:
        raise HTTPException(status_code=403, detail="Only group creator can delete the group")
    await session.delete(chat)
    await session.flush()
    return chat
