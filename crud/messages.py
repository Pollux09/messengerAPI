import uuid
from fastapi import HTTPException
from sqlalchemy import asc, select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from models.Message import Message
from schemas.chat import SendMessage, ChatId


async def get_last_chat_message(session: AsyncSession, chat_id: str | uuid.UUID):
    if isinstance(chat_id, str):
        try:
            chat_id = uuid.UUID(chat_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid chat ID format")

    stmt = (
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    result = await session.execute(stmt)
    message = result.scalars().first()
    return message


async def add_chat_message(session: AsyncSession, message: SendMessage):
    try:
        chat_id = (
            message.chat_id
            if isinstance(message.chat_id, uuid.UUID)
            else uuid.UUID(message.chat_id)
        )
        sender_id = (
            message.sender_user_id
            if isinstance(message.sender_user_id, uuid.UUID)
            else uuid.UUID(message.sender_user_id)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    created_message = Message(
        chat_id=chat_id,
        user_id=sender_id,
        text=message.text,
        message_type=message.message_type,
        encrypted_aes_key_receiver=message.encrypted_aes_key_receiver,
        encrypted_aes_key_sender=message.encrypted_aes_key_sender,
        iv=message.iv,
    )
    if not session.in_transaction():
        async with session.begin():
            session.add(created_message)
            await session.flush()
            await session.refresh(created_message)
    else:
        session.add(created_message)
        await session.flush()
        await session.refresh(created_message)

    return created_message


async def get_chat_messages(session: AsyncSession, chat_id: ChatId):
    try:
        chat_id_uuid = (
            chat_id.chat_id
            if isinstance(chat_id.chat_id, uuid.UUID)
            else uuid.UUID(chat_id.chat_id)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat ID format")

    stmt = select(Message).where(Message.chat_id == chat_id_uuid).order_by(asc(Message.created_at))
    result = await session.execute(stmt)
    messages = result.scalars().all()
    return messages
