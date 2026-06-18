import uuid

from sqlalchemy import UUID, Column, ForeignKey, String
from sqlalchemy.orm import relationship

from config.db import Base
from models.chat_member import ChatMember


class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String, nullable=False)
    title = Column(String, nullable=True)
    avatar_photo = Column(String, nullable=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    messages = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    members = relationship(
        "ChatMember",
        back_populates="chat",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="ChatMember.user_id",
    )

    @property
    def users_ids(self) -> list[uuid.UUID]:
        return [member.user_id for member in self.members]

    @users_ids.setter
    def users_ids(self, user_ids: list[uuid.UUID]) -> None:
        unique_user_ids = list(dict.fromkeys(user_ids))
        existing_members = {member.user_id: member for member in self.members}
        self.members = [
            existing_members.get(user_id, ChatMember(user_id=user_id))
            for user_id in unique_user_ids
        ]

    @property
    def users_count(self) -> int:
        return len(self.members)
