"""Attachment extraction model for OCR results."""
from sqlalchemy import Column, String, Boolean, ForeignKey, Integer, Float, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class AttachmentExtraction(BaseModel):
    """OCR extraction results from attachments."""

    __tablename__ = "attachmentextraction"

    request_id = Column("requestid", UUID(as_uuid=True), ForeignKey("request.id"), nullable=False, index=True)
    attachment_id = Column("attachmentid", UUID(as_uuid=True), ForeignKey("attachment.id"), index=True)

    is_certificate = Column("iscertificate", Boolean, default=False)
    classification_reason = Column("classificationreason", Text)
    detected_language = Column("detectedlanguage", String(50))

    belongs_to_bidder = Column("belongstobidder", Boolean)
    bidder_confidence_score = Column("bidderconfidencescore", Float)

    page_number = Column("pagenumber", Integer)
    total_pages = Column("totalpages", Integer)
    extraction_confidence = Column("extractionconfidence", Float)

    # Relationships
    attachment = relationship("Attachment", back_populates="extractions")
    certificates = relationship("Certificate", back_populates="attachment_extraction")

    def __repr__(self) -> str:
        return f"<AttachmentExtraction(id={self.id}, is_cert={self.is_certificate}, page={self.page_number})>"
