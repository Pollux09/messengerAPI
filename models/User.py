import uuid
from sqlalchemy import UUID, Column, String
from models.Basic import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    username = Column(String)
    hashed_password = Column(String)
    avatar_photo = Column(String)
    messages = relationship("Message", back_populates="user")
