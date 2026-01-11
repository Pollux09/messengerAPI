from sqlalchemy import UUID, Column, String
import uuid
from config.db import Base


class ChatType(Base):
    __tablename__ = "chat_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String)
    