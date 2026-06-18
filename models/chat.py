from sqlalchemy import ARRAY, UUID, Column, Integer, String
import uuid
from sqlalchemy.orm import relationship
from config.db import Base


class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    users_count = Column(Integer, index=True, default=2)
    type = Column(String)
    users_ids = Column(ARRAY(UUID(as_uuid=True)))
    messages = relationship(
        "Message",
        back_populates="chat", 
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    