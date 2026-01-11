from sqlalchemy import UUID, String, ForeignKey
import uuid
from sqlalchemy.orm import Mapped, mapped_column
from config.db import Base


class CryptoKeys(Base):
    __tablename__ = "crypto_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    public_key: Mapped[str] = mapped_column(String, nullable=False)
    private_key: Mapped[str] = mapped_column(String, nullable=False)