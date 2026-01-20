"""Base model with common fields."""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime, String, Boolean
from sqlalchemy.dialects.postgresql import UUID

from app.config.database import Base


class BaseModel(Base):
    """Abstract base model with common fields."""

    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=False)
    updated_by = Column(String(255))
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id={self.id})>"
