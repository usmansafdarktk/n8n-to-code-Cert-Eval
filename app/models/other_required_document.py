"""Other required document model (non-certificates like CVs, proposals)."""
from sqlalchemy import Column, String, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class OtherRequiredDocument(BaseModel):
    """Non-certificate documents (CVs, proposals, technical docs, etc)."""

    __tablename__ = "otherrequireddocument"

    request_id = Column("requestid", UUID(as_uuid=True), ForeignKey("request.id"), nullable=False, index=True)
    attachment_extraction_id = Column("attachmentextractionid", UUID(as_uuid=True), ForeignKey("attachmentextraction.id"), index=True)
    document_type_id = Column("documenttypeid", UUID(as_uuid=True), ForeignKey("certificatetype.id"), index=True)

    document_type = Column("documenttype", String(255))
    document_type_ar = Column("documenttypear", String(255))
    document_type_en = Column("documenttypeen", String(255))
    document_name = Column("documentname", String(500))

    extracted_entity_name = Column("extractedentityname", String(500))
    extracted_person_name = Column("extractedpersonname", String(500))

    match_confidence = Column("matchconfidence", Float)
    match_method = Column("matchmethod", String(100))
    match_details = Column("matchdetails", Text)

    key_information = Column("keyinformation", JSONB)  # Array of key extracted info

    detected_language = Column("detectedlanguage", String(50))
    summary = Column(Text)
    summary_ar = Column("summaryar", Text)
    summary_en = Column("summaryen", Text)

    classification_reason = Column("classificationreason", Text)

    # Relationships
    document_type = relationship("CertificateType", back_populates="other_documents")

    def __repr__(self) -> str:
        return f"<OtherRequiredDocument(id={self.id}, type={self.document_type}, name={self.document_name})>"
