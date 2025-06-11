import uuid
from fastapi import HTTPException
from psycopg2 import DatabaseError
from sqlalchemy import select, delete, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from passlib.context import CryptContext
from models.Chat import Chat
from models.Message import Message
from models.User import User
from schemas import ChatId, ChatScheme, DeleteChat, LoginData, SendMessage, UpdateUserAvatar, UserCreate, UserResponse, UsersIds

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def get_user(db: AsyncSession, user_id: str | uuid.UUID):
    # Convert to UUID only if input is a string
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this ID not found")
    return user

async def create_user(db: AsyncSession, user: UserCreate) -> User:
    hashed_password = pwd_context.hash(user.password)
    db_user = User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password,
    )
    db.add(db_user)
    await db.flush()
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def login_user(db: AsyncSession, login_data: LoginData):
    stmt = select(User).where(User.email == login_data.email)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this email not found")
    
    if not pwd_context.verify(login_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid password")
    return user

async def checkUserExists(db: AsyncSession, user_id: str | uuid.UUID):
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User with this ID not found")
    return True

async def getChatsList(db: AsyncSession, user_id: str | uuid.UUID):
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
        last_message = await get_last_chat_message(db=db, chat_id=chat.id)
        last_message_text = ""
        
        if last_message != None:
            if last_message.message_type == "image":
               last_message_text = "Изображение"
            else:
                last_message_text = last_message.text
        if user:
            chat_scheme = ChatScheme(
                id=chat.id,
                users_count=chat.users_count,
                type=chat.type,
                users_ids=chat.users_ids,
                another_user=UserResponse(
                    id=str(user.id),
                    email=user.email,
                    username=user.username,
                    avatar_photo=user.avatar_photo
                ),
                last_chat_message=last_message_text
            )
            chats_list.append(chat_scheme)
            
    return chats_list

async def get_last_chat_message(db: AsyncSession, chat_id: str | uuid.UUID):
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
    result = await db.execute(stmt)
    message = result.scalars().first()
    return message

async def getUserById(db: AsyncSession, user_id: str | uuid.UUID):
    if isinstance(user_id, str):
        try:
            user_id = uuid.UUID(user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    return user

async def search_users_by_username(db: AsyncSession, username: str):
    stmt = select(User).where(func.lower(User.username).ilike(f"%{username.lower()}%"))
    result = await db.execute(stmt)
    users = result.scalars().all()
    return users

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
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    user_ids = UsersIds(users_ids=[str(sender_id), str(recipient_id)])
    existing_chat = await find_chat_by_exact_users(db, user_ids)
    if existing_chat:
        raise HTTPException(status_code=400, detail="Chat with these users already exists")

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
                message_type=message.message_type
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
            message_type=message.message_type
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
    last_message_text = ""
    if last_message.message_type == "image":
        last_message_text = "Изображение"
    else:
        last_message_text = last_message.text
    
    if another_user_data:
        chat_scheme = ChatScheme(
            id=chat.id,
            users_count=chat.users_count,
            type=chat.type,
            users_ids=chat.users_ids,
            another_user=UserResponse(
                id=str(another_user_data.id),
                email=another_user_data.email,
                username=another_user_data.username,
                avatar_photo=another_user_data.avatar_photo
            ),
            last_chat_message=last_message_text
        )
        return {
            "messages": messages,
            "chat": chat_scheme,
            "current_user": UserResponse(
                id=str(current_user_data.id),
                email=current_user_data.email,
                username=current_user_data.username,
                avatar_photo=current_user_data.avatar_photo
            ),
        }
    raise HTTPException(status_code=400, detail="Failed to create chat")

async def add_chat_message(db: AsyncSession, message: SendMessage):
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
    )
    if not db.in_transaction():
        async with db.begin():
            db.add(created_message)
            await db.flush()
            await db.refresh(created_message)
    else:
        db.add(created_message)
        await db.flush()
        await db.refresh(created_message)
    
    return created_message

async def get_chat_messages(db: AsyncSession, chat_id: ChatId):
    try:
        chat_id_uuid = (
            chat_id.chat_id
            if isinstance(chat_id.chat_id, uuid.UUID)
            else uuid.UUID(chat_id.chat_id)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid chat ID format")
    
    stmt = select(Message).where(Message.chat_id == chat_id_uuid)
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return messages

async def add_user_avatar(db: AsyncSession, update_avatar: UpdateUserAvatar):
    # Проверка user_id
    if not isinstance(update_avatar.user_id, (uuid.UUID, str)):
        raise HTTPException(status_code=400, detail="User ID must be a UUID or a string")
    
    try:
        user_id = (
            update_avatar.user_id
            if isinstance(update_avatar.user_id, uuid.UUID)
            else uuid.UUID(update_avatar.user_id)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    # Проверка photo_data
    if not update_avatar.photo_data:
        raise HTTPException(status_code=400, detail="Photo data cannot be empty")
    
    try:
        async with db.begin():
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            user.avatar_photo = update_avatar.photo_data
        return user
    except DatabaseError:
        raise HTTPException(status_code=500, detail="Database error occurred")

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