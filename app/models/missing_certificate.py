"""Missing certificate model."""
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class MissingCertificate(BaseModel):
    """Tracks certificate types that were expected but not found."""

    __tablename__ = "missingcertificate"

    request_id = Column("requestid", UUID(as_uuid=True), ForeignKey("request.id"), nullable=False, index=True)
    certificate_type_id = Column("certificatetypeid", UUID(as_uuid=True), ForeignKey("certificatetype.id"), nullable=False, index=True)

    # Relationships
    request = relationship("Request", back_populates="missing_certificates")
    certificate_type = relationship("CertificateType", back_populates="missing_certificates")

    def __repr__(self) -> str:
        return f"<MissingCertificate(id={self.id}, request_id={self.request_id}, type_id={self.certificate_type_id})>"
