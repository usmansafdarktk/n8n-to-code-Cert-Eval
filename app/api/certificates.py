"""API endpoints for certificate and certificate type management."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID, uuid4

from app.config.database import get_db
from app.utils.auth import get_current_user
from app.schemas.certificate import (
    CertificateTypeCreate,
    CertificateTypeUpdate,
    CertificateTypeResponse,
    UpdateCertificateStatusRequest
)
from app.models.certificate_type import CertificateType
from app.models.certificate import Certificate
from loguru import logger

router = APIRouter(prefix="/api", tags=["certificates"])


# Certificate Type CRUD Endpoints

@router.get("/certificate-types", response_model=List[CertificateTypeResponse])
async def get_certificate_types(
    include_inactive: bool = False,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[CertificateTypeResponse]:
    """Get list of all certificate types.

    Args:
        include_inactive: Include inactive certificate types
        current_user: Authenticated user email
        db: Database session

    Returns:
        List of certificate types
    """
    try:
        query = select(CertificateType)

        if not include_inactive:
            query = query.where(CertificateType.is_active == True)

        query = query.order_by(CertificateType.name_en)

        result = await db.execute(query)
        cert_types = result.scalars().all()

        logger.info(f"Retrieved {len(cert_types)} certificate types")

        return [CertificateTypeResponse.model_validate(ct) for ct in cert_types]

    except Exception as e:
        logger.error(f"Failed to get certificate types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve certificate types: {str(e)}"
        )


@router.post("/certificate-types", response_model=CertificateTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_certificate_type(
    cert_type_data: CertificateTypeCreate,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> CertificateTypeResponse:
    """Create a new certificate type.

    Args:
        cert_type_data: Certificate type data
        current_user: Authenticated user email
        db: Database session

    Returns:
        Created certificate type
    """
    try:
        # Check if already exists
        result = await db.execute(
            select(CertificateType).where(
                CertificateType.name_en == cert_type_data.name_en
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Certificate type with name '{cert_type_data.name_en}' already exists"
            )

        # Create new certificate type
        cert_type = CertificateType(
            id=uuid4(),
            name_en=cert_type_data.name_en,
            name_ar=cert_type_data.name_ar,
            issuer=cert_type_data.issuer,
            is_active=True,
            created_by=current_user
        )

        db.add(cert_type)
        await db.commit()
        await db.refresh(cert_type)

        logger.info(f"Created certificate type: {cert_type.id} - {cert_type.name_en}")

        return CertificateTypeResponse.model_validate(cert_type)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create certificate type: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create certificate type: {str(e)}"
        )


@router.put("/certificate-types/{cert_type_id}", response_model=CertificateTypeResponse)
async def update_certificate_type(
    cert_type_id: UUID,
    cert_type_data: CertificateTypeUpdate,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> CertificateTypeResponse:
    """Update an existing certificate type.

    Args:
        cert_type_id: Certificate type ID
        cert_type_data: Update data
        current_user: Authenticated user email
        db: Database session

    Returns:
        Updated certificate type
    """
    try:
        # Find certificate type
        result = await db.execute(
            select(CertificateType).where(CertificateType.id == cert_type_id)
        )
        cert_type = result.scalar_one_or_none()

        if not cert_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Certificate type not found: {cert_type_id}"
            )

        # Update fields
        if cert_type_data.name_en is not None:
            cert_type.name_en = cert_type_data.name_en
        if cert_type_data.name_ar is not None:
            cert_type.name_ar = cert_type_data.name_ar
        if cert_type_data.issuer is not None:
            cert_type.issuer = cert_type_data.issuer

        cert_type.updated_by = current_user

        await db.commit()
        await db.refresh(cert_type)

        logger.info(f"Updated certificate type: {cert_type_id}")

        return CertificateTypeResponse.model_validate(cert_type)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update certificate type: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update certificate type: {str(e)}"
        )


@router.delete("/certificate-types/{cert_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certificate_type(
    cert_type_id: UUID,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Soft delete a certificate type (set is_active = false).

    Args:
        cert_type_id: Certificate type ID
        current_user: Authenticated user email
        db: Database session
    """
    try:
        # Find certificate type
        result = await db.execute(
            select(CertificateType).where(CertificateType.id == cert_type_id)
        )
        cert_type = result.scalar_one_or_none()

        if not cert_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Certificate type not found: {cert_type_id}"
            )

        # Soft delete
        cert_type.is_active = False
        cert_type.updated_by = current_user

        await db.commit()

        logger.info(f"Deleted (soft) certificate type: {cert_type_id}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete certificate type: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete certificate type: {str(e)}"
        )


# Certificate Status Update Endpoint

@router.post("/certificates/{certificate_id}/update-status")
async def update_certificate_status(
    certificate_id: UUID,
    status_update: UpdateCertificateStatusRequest,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually update the validation status of a certificate.

    Args:
        certificate_id: Certificate ID
        status_update: New validation status and reason
        current_user: Authenticated user email
        db: Database session

    Returns:
        Success message
    """
    try:
        # Find certificate
        result = await db.execute(
            select(Certificate).where(Certificate.id == certificate_id)
        )
        certificate = result.scalar_one_or_none()

        if not certificate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Certificate not found: {certificate_id}"
            )

        # Update status
        certificate.validation_status = status_update.validation_status
        certificate.is_manually_validated = True
        certificate.manual_validation_reason = status_update.manual_validation_reason
        certificate.manually_validated_by = current_user
        certificate.manually_validated_at = db.func.now()

        await db.commit()

        logger.info(
            f"Manually updated certificate {certificate_id} status to "
            f"{status_update.validation_status} by {current_user}"
        )

        return {
            "success": True,
            "message": "Certificate status updated successfully",
            "certificate_id": str(certificate_id),
            "new_status": status_update.validation_status
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update certificate status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update certificate status: {str(e)}"
        )
