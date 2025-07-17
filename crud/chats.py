import uuid
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from crud.users import getUserById
from crud.messages import get_last_chat_message
from crud.crypto_keys import get_user_crypto_keys
from models import Message
from models.Chat import Chat
from schemas import ChatScheme, NewMessage, UserResponse, UsersIds, SendMessage, DeleteChat


async def getChatsList(db: AsyncSession, user_id: str | uuid.UUID):
    try:
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid user ID format")

        stmt = select(Chat).where(Chat.users_ids.any(user_id))
        result = await db.execute(stmt)
        chats = result.scalars().all()

        chats_list = []
        for chat in chats:
            if user_id not in chat.users_ids:
                continue

            another_user_id = next((x for x in chat.users_ids if x != user_id), None)
            if not another_user_id:
                continue

            user = await getUserById(db=db, user_id=another_user_id)
            if not user:
                print(f"[WARN] User with ID {another_user_id} not found.")
                continue

            last_message_raw = await get_last_chat_message(db=db, chat_id=chat.id)
            if not last_message_raw:
                print(f"[INFO] No last message found for chat {chat.id}")
                continue
            else:
                try:
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
                except AttributeError as e:
                    print(f"[ERROR] Failed to construct NewMessage for chat {chat.id}: {e}")
                    continue

            keys = await get_user_crypto_keys(db=db, user_id=user.id)
            if not keys:
                print(f"[WARN] No crypto keys for user {user.id}")
                continue

            chat_scheme = ChatScheme(
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
                last_chat_message=last_message
            )
            chats_list.append(chat_scheme)

        return chats_list

    except Exception as e:
        print(f"[FATAL] Unexpected error in getChatsList: {e}")
        raise


async def find_chat_by_exact_users(db: AsyncSession, user_ids: UsersIds):
    try:
        user_uuid_list = [
            uid if isinstance(uid, uuid.UUID) else uuid.UUID(uid)
            for uid in user_ids.users_ids
        ]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    stmt = (
        select(Chat)
        .where(
            Chat.users_ids.op('@>')(user_uuid_list),
            Chat.users_ids.op('<@')(user_uuid_list)
        )
        .options(selectinload(Chat.messages))
    )
    result = await db.execute(stmt)
    chat = result.scalars().first()
    return chat


async def create_chat(db: AsyncSession, message: SendMessage):
    try:
        sender_id = (
            message.sender_user_id
            if isinstance(message.sender_user_id, uuid.UUID)
            else uuid.UUID(message.sender_user_id)
        )
        recipient_id = (
            message.recipient_user_id
            if isinstance(message.recipient_user_id, uuid.UUID)
            else uuid.UUID(message.recipient_user_id)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user_ids = UsersIds(users_ids=[str(sender_id), str(recipient_id)])
    existing_chat = await find_chat_by_exact_users(db, user_ids)
    if existing_chat:
        raise HTTPException(status_code=400, detail="Chat with these users already exists")

    chat = Chat(
        users_count=2,
        type="private",
        users_ids=[sender_id, recipient_id]
    )
    if not db.in_transaction():
        async with db.begin():
            db.add(chat)
            await db.commit()
            await db.refresh(chat)
    else:
        db.add(chat)
        await db.commit()
        await db.refresh(chat)
    return chat


async def create_chat_by_initial_message(db: AsyncSession, message: SendMessage):
    try:
        sender_id = (
            message.sender_user_id
            if isinstance(message.sender_user_id, uuid.UUID)
            else uuid.UUID(message.sender_user_id)
        )
        recipient_id = (
            message.recipient_user_id
            if isinstance(message.recipient_user_id, uuid.UUID)
            else uuid.UUID(message.recipient_user_id)
        )
    except ValueError:
        raise HTTPException(status_code=402, detail="Invalid user ID format")

    user_ids = UsersIds(users_ids=[str(sender_id), str(recipient_id)])
    existing_chat = await find_chat_by_exact_users(db, user_ids)
    if existing_chat:
        raise HTTPException(status_code=404, detail="Chat with these users already exists")

    if not db.in_transaction():
        async with db.begin():
            chat = Chat(
                users_count=2,
                type="private",
                users_ids=[sender_id, recipient_id]
            )
            db.add(chat)
            await db.flush()
            created_message = Message(
                chat_id=chat.id,
                user_id=sender_id,
                text=message.text,
                message_type=message.message_type,
                encrypted_aes_key_receiver=message.encrypted_aes_key_receiver,
                encrypted_aes_key_sender=message.encrypted_aes_key_sender,
                iv=message.iv,
            )
            db.add(created_message)
            await db.refresh(chat)
            await db.refresh(created_message)
    else:
        chat = Chat(
            users_count=2,
            type="private",
            users_ids=[sender_id, recipient_id]
        )
        db.add(chat)
        await db.flush()
        created_message = Message(
            chat_id=chat.id,
            user_id=sender_id,
            text=message.text,
            message_type=message.message_type,
            encrypted_aes_key_receiver=message.encrypted_aes_key_receiver,
            encrypted_aes_key_sender=message.encrypted_aes_key_sender,
            iv=message.iv,
        )
        db.add(created_message)
        await db.commit()
        await db.refresh(chat)
        await db.refresh(created_message)

    stmt = select(Message).where(Message.chat_id == chat.id)
    result = await db.execute(stmt)
    messages = result.scalars().all()

    another_user_id = next((x for x in chat.users_ids if x != sender_id), None)
    current_user_id = next((x for x in chat.users_ids if x != recipient_id), None)

    another_user_data = await getUserById(db=db, user_id=another_user_id)
    current_user_data = await getUserById(db=db, user_id=current_user_id)

    last_message = await get_last_chat_message(db=db, chat_id=chat.id)

    if another_user_data:
        keys = await get_user_crypto_keys(db=db, user_id=another_user_data.id);
        chat_scheme = ChatScheme(
            id=chat.id,
            users_count=chat.users_count,
            type=chat.type,
            users_ids=chat.users_ids,
            another_user=UserResponse(
                id=str(another_user_data.id),
                email=another_user_data.email,
                username=another_user_data.username,
                avatar_photo=another_user_data.avatar_photo,
                user_public_key=keys.public_key,
            ),
            last_chat_message=NewMessage(
                id=last_message.id,
                chat_id=last_message.chat_id,
                user_id=last_message.user_id,
                text=last_message.text,
                created_at=last_message.created_at,
                message_type=last_message.message_type,
                encrypted_aes_key_sender=last_message.encrypted_aes_key_sender,
                encrypted_aes_key_receiver=last_message.encrypted_aes_key_receiver,
                iv=last_message.iv,
            )
        )
        keys = await get_user_crypto_keys(db=db, user_id=current_user_data.id);

        return {
            "messages": messages,
            "chat": chat_scheme,
            "current_user": UserResponse(
                id=str(current_user_data.id),
                email=current_user_data.email,
                username=current_user_data.username,
                avatar_photo=current_user_data.avatar_photo,
                user_public_key=keys.public_key,
            ),
        }
    raise HTTPException(status_code=408, detail="Failed to create chat")


async def delete_chat_by_id(db: AsyncSession, chat_id: DeleteChat):
    try:
        chat_id_uuid = (
            chat_id.chat_id
            if isinstance(chat_id.chat_id, uuid.UUID)
            else uuid.UUID(chat_id.chat_id)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat ID format")

    if not db.in_transaction():
        async with db.begin():
            result = await db.execute(select(Chat).where(Chat.id == chat_id_uuid))
            chat = result.scalar_one_or_none()
            if not chat:
                raise HTTPException(status_code=404, detail="Chat not found")

            await db.delete(chat)
            await db.commit()
    else:
        result = await db.execute(select(Chat).where(Chat.id == chat_id_uuid))
        chat = result.scalar_one_or_none()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat not found")

        await db.delete(chat)
        await db.commit()
    return {"detail": "Chat deleted successfully"}
