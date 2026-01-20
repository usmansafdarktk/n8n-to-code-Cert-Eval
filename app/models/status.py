"""Status lookup table model."""
from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4

from app.config.database import Base


class Status(Base):
    """Status lookup table for request status codes."""

    __tablename__ = "status"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    label_en = Column("labelen", String(255))
    label_ar = Column("labelar", String(255))
    description = Column(Text)

    def __repr__(self) -> str:
        return f"<Status(code={self.code}, label_en={self.label_en})>"
