"""Request note model for user comments."""
from sqlalchemy import Column, String, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from app.config.database import Base


class RequestNote(Base):
    """User notes on validation requests."""

    __tablename__ = "requests_note"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    request_id = Column(UUID(as_uuid=True), ForeignKey("request.id"), nullable=False, index=True)
    note = Column(Text, nullable=False)
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    request = relationship("Request", back_populates="notes")

    def __repr__(self) -> str:
        return f"<RequestNote(id={self.id}, request_id={self.request_id}, created_by={self.created_by})>"
