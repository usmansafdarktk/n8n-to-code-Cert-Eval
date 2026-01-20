"""Pydantic schemas for validation request operations."""
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID


class FileInput(BaseModel):
    """Input schema for file in validation request."""
    id: UUID
    file_name: str = Field(..., alias="fileName")
    document_role: str = "certificate"
    signed_url: str


class StartProcessingRequest(BaseModel):
    """Schema for starting certificate validation process."""
    rfp_number: str = Field(..., max_length=255)
    bidder_name: str = Field(..., max_length=500)
    warning_start_date: Optional[date] = None
    warning_end_date: Optional[date] = None
    certificate_types: List[dict] = Field(default_factory=list)
    files: List[FileInput]

    @field_validator('files')
    @classmethod
    def validate_files(cls, v: List[FileInput]) -> List[FileInput]:
        if not v:
            raise ValueError('At least one file is required')
        return v


class RequestNoteCreate(BaseModel):
    """Schema for creating a note on a request."""
    request_id: UUID
    note: str = Field(..., min_length=1)


class RequestNoteResponse(BaseModel):
    """Schema for request note response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    note: str
    created_by: str
    created_at: datetime


class RequestSummaryResponse(BaseModel):
    """Schema for request summary (list view)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rfp_number: str
    bidder_name: str
    status_code: str
    total_certificates: Optional[int] = 0
    passed_certificates: Optional[int] = 0
    failed_certificates: Optional[int] = 0
    warning_certificates: Optional[int] = 0
    missing_certificates_count: Optional[int] = 0
    created_date: datetime
    completed_date: Optional[datetime] = None
    user_email: Optional[str] = None


class ValidationSummary(BaseModel):
    """Validation summary statistics."""
    total_processed: int
    total_certificates: int
    skipped_non_certificates: int
    passed: int
    warnings: int
    failed: int
    valid_certificates: int
    expired_certificates: int
    in_warning_period: int
    expected_certificate_types_count: int
    matched_certificate_types_count: int
    missing_certificate_types_count: int
    missing_certificate_types: List[dict]
    rfp_number: str
    bidder_name: str
    timestamp: datetime


class RequestDetailedResponse(BaseModel):
    """Schema for detailed request response."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rfp_number: str
    bidder_name: str
    status_code: str
    summary: Optional[str] = None
    warning_start_date: Optional[datetime] = None
    warning_end_date: Optional[datetime] = None
    created_date: datetime
    completed_date: Optional[datetime] = None
    user_email: Optional[str] = None

    # Related data
    certificates: List[dict] = Field(default_factory=list)
    missing_certificates: List[dict] = Field(default_factory=list)
    other_documents: List[dict] = Field(default_factory=list)
    notes: List[dict] = Field(default_factory=list)
    validation_summary: Optional[ValidationSummary] = None
