import uuid
from sqlalchemy import UUID, Column, String
from sqlalchemy.orm import relationship, Mapped
from config.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = Column(String, unique=True, index=True)
    username: Mapped[str] = Column(String)
    hashed_password: Mapped[str] = Column(String)
    avatar_photo: Mapped[str] = Column(String)
    messages = relationship("Message", back_populates="user")
