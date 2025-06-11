from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel

from models.User import User

class UserCreate(BaseModel):
    email: str
    password: str
    username: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    avatar_photo: Optional[str] = None
    
class AccessToken(BaseModel):
    access_token: str
    
class RefreshToken(BaseModel):
    refresh_token: str
    
class LoginData(BaseModel):
    email: str
    password: str
    
class UserId(BaseModel):
    user_id: str
    
class ChatScheme(BaseModel):
    id: UUID
    users_count: int
    type: str
    users_ids: List[UUID]
    another_user: UserResponse
    last_chat_message: str
    
class FindUsersByUsername(BaseModel):
    username: str
    
class FindedUser(BaseModel):
    id: UUID
    username: str
    
class Message(BaseModel):
    id: UUID
    sender_user_id: UUID
    type: str
    isReaded: bool
    
class SendMessage(BaseModel):
    sender_user_id: UUID
    recipient_user_id: UUID
    chat_id: Optional[str] = None
    text: str
    message_type: str
    
class NewMessage(BaseModel):
    id: UUID
    chat_id: Any
    user_id: UUID
    text: str
    created_at: datetime
    message_type: str
    
class UsersIds(BaseModel):
    users_ids: List

class ChatId(BaseModel):
    chat_id: UUID
    
class UpdateUserAvatar(BaseModel):
    user_id: UUID
    photo_data: str


class DeleteChat(BaseModel):
    chat_id: UUID
    another_user_id: UUID