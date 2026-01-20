"""Certificate model for validated certificates."""
from sqlalchemy import Column, String, Date, Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Certificate(BaseModel):
    """Validated certificate entity."""

    __tablename__ = "certificate"

    request_id = Column("requestid", UUID(as_uuid=True), ForeignKey("request.id"), nullable=False, index=True)
    attachment_extraction_id = Column("attachmentextractionid", UUID(as_uuid=True), ForeignKey("attachmentextraction.id"), index=True)
    certificate_type_id = Column("certificatetypeid", UUID(as_uuid=True), ForeignKey("certificatetype.id"), index=True)

    extracted_bidder_name = Column("extractedbiddername", String(500))
    certificate_name = Column("certificatename", String(500))
    issuer_name = Column("issuername", String(500))
    issue_date = Column("issuedate", Date)
    expiry_date = Column("expirydate", Date)

    validation_status = Column("validationstatus", String(50), nullable=False)  # Valid/Invalid/Warning
    validation_issues = Column("validationissues", JSONB)  # Array of issue objects
    validation_warnings = Column("validationwarnings", JSONB)  # Array of warning objects

    is_manually_validated = Column("ismanuallyvalidated", Boolean, default=False)
    manual_validation_reason = Column("manualvalidationreason", Text)
    manual_validated_by = Column("manualvalidatedby", String(255))
    manual_validated_date = Column("manualvalidateddate", Date)

    # Relationships
    request = relationship("Request", back_populates="certificates")
    certificate_type = relationship("CertificateType", back_populates="certificates")
    attachment_extraction = relationship("AttachmentExtraction", back_populates="certificates")

    def __repr__(self) -> str:
        return f"<Certificate(id={self.id}, name={self.certificate_name}, status={self.validation_status})>"
