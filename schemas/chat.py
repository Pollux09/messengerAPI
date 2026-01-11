from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel
from schemas.user import UserResponse


class ChatId(BaseModel):
    id: int


class UpdateUserAvatar(BaseModel):
    user_id: UUID
    photo_data: str


class DeleteChat(BaseModel):
    chat_id: UUID
    another_user_id: UUID


class NewMessage(BaseModel):
    id: UUID
    chat_id: Any
    user_id: UUID
    text: str
    created_at: datetime
    message_type: str
    encrypted_aes_key_sender: str
    encrypted_aes_key_receiver: str
    iv: str


class ChatScheme(BaseModel):
    id: UUID
    users_count: int
    type: str
    users_ids: list[UUID]
    another_user: UserResponse
    last_chat_message: NewMessage


class Message(BaseModel):
    id: UUID
    sender_user_id: UUID
    type: str
    is_read: bool


class SendMessage(BaseModel):
    sender_user_id: UUID
    recipient_user_id: UUID
    chat_id: Optional[str] = None
    text: str
    message_type: str
    encrypted_aes_key_sender: str
    encrypted_aes_key_receiver: str
    iv: str
