from sqlalchemy import ARRAY, UUID, Column, Integer, String, DateTime, func
from models.Basic import Base
import uuid
from sqlalchemy.orm import relationship

class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    users_count = Column(Integer, index=True)
    type = Column(String)
    users_ids = Column(ARRAY(UUID(as_uuid=True)))
    messages = relationship(
        "Message",
        back_populates="chat", 
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    