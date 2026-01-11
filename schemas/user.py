from typing import Optional
from pydantic import BaseModel
from uuid import UUID

class UserId(BaseModel):
    user_id: str


class UsersIds(BaseModel):
    users_ids: list[UUID]


class FindUsersByUsername(BaseModel):
    username: str


class FindedUser(BaseModel):
    id: UUID
    username: str


class UserCreate(BaseModel):
    email: str
    password: str
    username: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    avatar_photo: Optional[str] = None
    user_public_key: str