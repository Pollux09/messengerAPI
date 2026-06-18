from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from schemas.user import UserResponse


class ChatId(BaseModel):
    chat_id: UUID


class UpdateUserAvatar(BaseModel):
    user_id: UUID
    photo_data: str


class UpdateChatAvatar(BaseModel):
    chat_id: UUID
    photo_data: str


class DeleteChat(BaseModel):
    chat_id: UUID
    another_user_id: Optional[UUID] = None


class NewMessage(BaseModel):
    id: UUID
    chat_id: Any
    user_id: UUID
    text: str
    created_at: datetime
    message_type: str
    encrypted_aes_key_sender: str
    encrypted_aes_key_receiver: str
    encrypted_keys: dict[str, str] = {}
    iv: str


class ChatScheme(BaseModel):
    id: UUID
    users_count: int
    type: str
    users_ids: list[UUID]
    title: Optional[str] = None
    avatar_photo: Optional[str] = None
    created_by: Optional[UUID] = None
    participants: list[UserResponse]
    another_user: Optional[UserResponse] = None
    last_chat_message: Optional[NewMessage] = None
    can_manage: bool = False


class Message(BaseModel):
    id: UUID
    sender_user_id: UUID
    type: str
    is_read: bool


class SendMessage(BaseModel):
    sender_user_id: UUID
    recipient_user_id: Optional[UUID] = None
    chat_id: Optional[str] = None
    text: str
    message_type: str
    encrypted_aes_key_sender: str = ""
    encrypted_aes_key_receiver: str = ""
    encrypted_keys: dict[str, str] = {}
    iv: str


class CreateGroupChat(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    user_ids: list[UUID] = Field(default_factory=list)


class UpdateGroupTitle(BaseModel):
    chat_id: UUID
    title: str = Field(min_length=1, max_length=128)


class GroupMembersUpdate(BaseModel):
    chat_id: UUID
    user_ids: list[UUID] = Field(min_length=1)


class GroupMemberRemove(BaseModel):
    chat_id: UUID
    user_id: UUID
