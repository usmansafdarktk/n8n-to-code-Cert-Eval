"""Certificate type model (master data)."""
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class CertificateType(BaseModel):
    """Master data for certificate types."""

    __tablename__ = "certificatetype"

    name_en = Column("nameen", String(500))
    name_ar = Column("namear", String(500))
    issuer = Column(String(500))

    # Relationships
    certificates = relationship("Certificate", back_populates="certificate_type")
    missing_certificates = relationship("MissingCertificate", back_populates="certificate_type")
    other_documents = relationship("OtherRequiredDocument", back_populates="document_type")

    def __repr__(self) -> str:
        return f"<CertificateType(id={self.id}, name_en={self.name_en}, name_ar={self.name_ar})>"
