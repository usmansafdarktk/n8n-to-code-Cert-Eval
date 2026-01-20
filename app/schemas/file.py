"""Pydantic schemas for file operations."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID


class FileUploadResponse(BaseModel):
    """Response schema for file upload."""
    file_id: UUID
    storage_path: str
    signed_url: str
    file_hash: str
    file_size: int
    filename: str
    uploaded_at: datetime


class SignedUrlResponse(BaseModel):
    """Response schema for signed URL generation."""
    file_id: UUID
    signed_url: str
    expires_at: datetime
    storage_path: str


class FileMetadata(BaseModel):
    """File metadata schema."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: UUID
    filename: str
    storage_path: str
    file_hash: str
    file_size: int
    signed_url: Optional[str] = None
    document_role: str
    uploaded_by: str
    uploaded_at: datetime
