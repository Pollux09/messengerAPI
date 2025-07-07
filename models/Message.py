from sqlalchemy import UUID, Column, ForeignKey, DateTime, Text, func
from models.Basic import Base
import uuid
from sqlalchemy.orm import relationship

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False)
    chat = relationship("Chat", back_populates="messages")

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="messages")

    text = Column(Text, nullable=False)
    encrypted_aes_key_sender = Column(Text, nullable=False)
    encrypted_aes_key_receiver = Column(Text, nullable=False)
    iv = Column(Text, nullable=False)
    
    message_type = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())