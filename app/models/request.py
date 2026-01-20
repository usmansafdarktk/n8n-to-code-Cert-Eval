"""Request model for certificate validation requests."""
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class Request(BaseModel):
    """Main request entity for certificate validation."""

    __tablename__ = "request"

    rfp_number = Column("rfpnumber", String(255), nullable=False, index=True)
    bidder_name = Column("biddername", String(500), nullable=False)
    warning_start_date = Column("warningstartdate", DateTime)
    warning_end_date = Column("warningenddate", DateTime)
    status_code = Column("statuscode", String(50), nullable=False, default="PENDING", index=True)
    summary = Column(Text)
    completed_date = Column("completeddate", DateTime)
    user_email = Column(String(255), index=True)

    # Relationships
    attachments = relationship("Attachment", back_populates="request", cascade="all, delete-orphan")
    certificates = relationship("Certificate", back_populates="request", cascade="all, delete-orphan")
    missing_certificates = relationship("MissingCertificate", back_populates="request", cascade="all, delete-orphan")
    notes = relationship("RequestNote", back_populates="request", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Request(id={self.id}, rfp={self.rfp_number}, bidder={self.bidder_name}, status={self.status_code})>"
