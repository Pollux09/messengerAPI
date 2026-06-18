from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from uuid import UUID


class UserId(BaseModel):
    user_id: str


class UsersIds(BaseModel):
    users_ids: list[UUID]


class SearchUsersRequest(BaseModel):
    query: str = Field(min_length=1, max_length=64)


class FindedUser(BaseModel):
    id: UUID
    username: str


class UpdateUsername(BaseModel):
    username: str = Field(min_length=3, max_length=32)


class UpdateProfile(BaseModel):
    nickname: str = Field(min_length=1, max_length=64)
    phone_number: str | None = Field(default=None, max_length=32)


class RoleCreate(BaseModel):
    title: str = Field(min_length=1, max_length=64)
    is_admin: bool = False


class RoleUpdate(BaseModel):
    role_id: UUID


class RegistrationDecision(BaseModel):
    user_id: UUID
    rejection_reason: str | None = Field(default=None, max_length=255)


class RoleResponse(BaseModel):
    id: UUID
    title: str
    is_admin: bool
    is_default: bool = False


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    nickname: str
    phone_number: Optional[str] = None
    avatar_photo: Optional[str] = None
    user_public_key: str
    is_admin: bool = False
    is_online: bool = False
    registration_status: str = "approved"
    rejection_reason: Optional[str] = None
    role_id: Optional[UUID] = None
    role_title: Optional[str] = None
    last_seen_at: Optional[datetime] = None
