"""Attachment model for uploaded files."""
from sqlalchemy import Column, String, BigInteger, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Attachment(BaseModel):
    """Uploaded file attachment."""

    __tablename__ = "attachment"

    request_id = Column("requestid", UUID(as_uuid=True), ForeignKey("request.id"), nullable=True, index=True)
    name = Column(String(500), nullable=False)
    file_hash = Column("filehash", String(255), nullable=False, unique=True, index=True)
    storage_path = Column("storagepath", String(1000), nullable=False)
    signed_url = Column("signedurl", String(2000))
    signed_url_expires_date = Column("signedurlexpiresdate", DateTime)
    file_type = Column("filetype", String(50), nullable=False)
    file_size_bytes = Column("filesizebytes", BigInteger)
    content_type = Column("contenttype", String(100))

    # Relationships
    request = relationship("Request", back_populates="attachments")
    extractions = relationship("AttachmentExtraction", back_populates="attachment", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Attachment(id={self.id}, name={self.name}, hash={self.file_hash[:8]})>"
