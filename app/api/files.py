"""API endpoints for file operations."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from app.config.database import get_db
from app.utils.auth import get_current_user
from app.schemas.file import FileUploadResponse, SignedUrlResponse
from app.models.attachment import Attachment
from app.services.file_storage import FileStorageService
from app.services.zip_handler import ZipHandlerService
from app.config.settings import settings
from loguru import logger

router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> FileUploadResponse:
    """Upload a file to Google Cloud Storage.

    Supports individual files (PDF, PNG, JPG, JPEG) and ZIP archives.
    ZIP files will be extracted and all supported files will be uploaded.

    Args:
        file: File to upload (can be PDF, image, or ZIP)
        current_user: Authenticated user email
        db: Database session

    Returns:
        Upload response with file metadata and signed URL
    """
    try:
        logger.info(f"Uploading file: {file.filename}")

        # Read file content
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size
        max_size = settings.max_upload_size_mb * 1024 * 1024
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {settings.max_upload_size_mb}MB"
            )

        # Check if it's a ZIP file
        zip_handler = ZipHandlerService()

        if zip_handler.is_zip_file(file.filename, file_content):
            logger.info(f"Detected ZIP archive: {file.filename}")

            # Validate ZIP
            is_valid, error_msg = zip_handler.validate_zip_archive(file_content)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid ZIP file: {error_msg}"
                )

            # Extract files from ZIP
            extracted_files = zip_handler.extract_files_from_zip(
                zip_content=file_content,
                original_filename=file.filename
            )

            if not extracted_files:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No valid files found in ZIP archive"
                )

            # Upload all extracted files
            storage_service = FileStorageService()
            uploaded_files = []

            for extracted_file in extracted_files:
                storage_path, signed_url, file_hash = await storage_service.upload_file(
                    file_content=extracted_file['content'],
                    filename=extracted_file['filename']
                )

                uploaded_files.append({
                    'file_id': str(extracted_file['id']),
                    'filename': extracted_file['filename'],
                    'storage_path': storage_path,
                    'signed_url': signed_url,
                    'file_hash': file_hash,
                    'file_size': extracted_file['size']
                })

            logger.info(f"Uploaded {len(uploaded_files)} files from ZIP: {file.filename}")

            # Return info about the first file (for backward compatibility)
            # In practice, you might want to return all files
            return FileUploadResponse(
                file_id=UUID(uploaded_files[0]['file_id']),
                storage_path=uploaded_files[0]['storage_path'],
                signed_url=uploaded_files[0]['signed_url'],
                file_hash=uploaded_files[0]['file_hash'],
                file_size=uploaded_files[0]['file_size'],
                filename=f"{file.filename} ({len(uploaded_files)} files extracted)",
                uploaded_at=datetime.utcnow()
            )

        else:
            # Handle single file upload
            # Validate file type
            if file.filename:
                file_ext = file.filename.rsplit('.', 1)[-1].lower()
                allowed_types = settings.allowed_file_types.split(',')

                if file_ext not in allowed_types:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File type '.{file_ext}' not allowed. "
                               f"Allowed types: {settings.allowed_file_types}, zip"
                    )

            # Upload to GCS
            storage_service = FileStorageService()
            storage_path, signed_url, file_hash = await storage_service.upload_file(
                file_content=file_content,
                filename=file.filename,
                content_type=file.content_type
            )

            file_id = uuid4()

            logger.info(
                f"File uploaded successfully: {file_id}, "
                f"path: {storage_path}, size: {file_size}"
            )

            return FileUploadResponse(
                file_id=file_id,
                storage_path=storage_path,
                signed_url=signed_url,
                file_hash=file_hash,
                file_size=file_size,
                filename=file.filename,
                uploaded_at=datetime.utcnow()
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.get("/{file_id}/signed-url", response_model=SignedUrlResponse)
async def get_signed_url(
    file_id: UUID,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    expiration_days: int = None
) -> SignedUrlResponse:
    """Get or regenerate a signed URL for a file.

    Args:
        file_id: File/attachment ID
        current_user: Authenticated user email
        db: Database session
        expiration_days: Optional custom expiration (default from settings)

    Returns:
        Signed URL response with expiration
    """
    try:
        # Find the attachment
        result = await db.execute(
            select(Attachment).where(Attachment.id == file_id)
        )
        attachment = result.scalar_one_or_none()

        if not attachment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {file_id}"
            )

        # Generate new signed URL
        storage_service = FileStorageService()

        if expiration_days is None:
            expiration_days = settings.signed_url_expiration_days

        signed_url = await storage_service.generate_signed_url(
            storage_path=attachment.storage_path,
            expiration_days=expiration_days
        )

        # Update attachment record
        attachment.signed_url = signed_url
        attachment.signed_url_expires_at = datetime.utcnow() + timedelta(days=expiration_days)

        await db.commit()

        logger.info(
            f"Generated signed URL for file {file_id}, "
            f"expires in {expiration_days} days"
        )

        return SignedUrlResponse(
            file_id=file_id,
            signed_url=signed_url,
            expires_at=attachment.signed_url_expires_at,
            storage_path=attachment.storage_path
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate signed URL: {str(e)}"
        )
