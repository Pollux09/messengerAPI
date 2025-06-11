from sqlalchemy import UUID, Column, String
from models.Basic import Base
import uuid

class Chat_type(Base):
    __tablename__ = "chat_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String)
    