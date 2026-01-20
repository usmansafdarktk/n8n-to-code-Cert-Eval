"""Pydantic schemas for certificate-related operations."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID


class CertificateTypeBase(BaseModel):
    """Base schema for certificate type."""
    name_en: Optional[str] = Field(None, max_length=500)
    name_ar: Optional[str] = Field(None, max_length=500)
    issuer: Optional[str] = Field(None, max_length=500)


class CertificateTypeCreate(CertificateTypeBase):
    """Schema for creating certificate type."""
    created_by: str = Field(..., max_length=255)


class CertificateTypeUpdate(CertificateTypeBase):
    """Schema for updating certificate type."""
    updated_by: str = Field(..., max_length=255)


class CertificateTypeResponse(CertificateTypeBase):
    """Schema for certificate type response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_date: datetime
    updated_date: Optional[datetime] = None


class ValidationIssue(BaseModel):
    """Validation issue or warning."""
    code: str
    name: str
    name_ar: str
    severity: str  # error/warning
    description: str
    description_ar: str


class CertificateBase(BaseModel):
    """Base schema for certificate."""
    certificate_name: Optional[str] = Field(None, max_length=500)
    issuer_name: Optional[str] = Field(None, max_length=500)
    extracted_bidder_name: Optional[str] = Field(None, max_length=500)
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None


class CertificateResponse(CertificateBase):
    """Schema for certificate response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    certificate_type_id: Optional[UUID] = None
    validation_status: str
    validation_issues: Optional[List[ValidationIssue]] = None
    validation_warnings: Optional[List[ValidationIssue]] = None
    is_manually_validated: bool
    created_date: datetime


class MissingCertificateResponse(BaseModel):
    """Schema for missing certificate response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    certificate_type_id: UUID
    certificate_type_name_en: Optional[str] = None
    certificate_type_name_ar: Optional[str] = None
    status: str = "missing"
    status_ar: str = "مفقود"


class OtherDocumentResponse(BaseModel):
    """Schema for other required document response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    document_type: Optional[str] = None
    document_type_ar: Optional[str] = None
    document_type_en: Optional[str] = None
    document_name: Optional[str] = None
    extracted_person_name: Optional[str] = None
    match_confidence: Optional[float] = None
    match_method: Optional[str] = None
    summary: Optional[str] = None
    created_date: datetime


class UpdateCertificateStatusRequest(BaseModel):
    """Request schema for manually updating certificate validation status."""
    validation_status: str = Field(..., pattern="^(PASSED|WARNING|FAILED)$")
    manual_validation_reason: str = Field(..., min_length=1, max_length=1000)
