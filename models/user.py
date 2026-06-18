import uuid

from sqlalchemy import UUID, Column, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.sql import func

from config.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = Column(String, unique=True, index=True, nullable=False)
    username: Mapped[str] = Column(String, unique=True, index=True, nullable=False)
    nickname: Mapped[str] = Column(String, nullable=False)
    phone_number: Mapped[str | None] = Column(String, nullable=True)
    hashed_password: Mapped[str] = Column(String, nullable=False)
    avatar_photo: Mapped[str | None] = Column(String, nullable=True)
    registration_status: Mapped[str] = Column(
        String,
        nullable=False,
        default="pending",
        server_default="pending",
    )
    rejection_reason: Mapped[str | None] = Column(String, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True, server_default=func.now())
    role_id: Mapped[uuid.UUID] = Column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    role = relationship("Role", back_populates="users")
    messages = relationship("Message", back_populates="user")
    chat_members = relationship(
        "ChatMember",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
