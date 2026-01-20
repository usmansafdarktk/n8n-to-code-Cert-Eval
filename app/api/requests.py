"""API endpoints for request management and reporting."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Dict, Any
from uuid import UUID

from app.config.database import get_db
from app.utils.auth import get_current_user
from app.schemas.request import (
    RequestSummaryResponse,
    RequestDetailedResponse,
    RequestNoteCreate,
    RequestNoteResponse
)
from app.schemas.certificate import (
    CertificateResponse,
    MissingCertificateResponse,
    OtherDocumentResponse
)
from app.models.request import Request
from app.models.certificate import Certificate
from app.models.missing_certificate import MissingCertificate
from app.models.other_required_document import OtherRequiredDocument
from app.models.request_note import RequestNote
from loguru import logger

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.get("/summary", response_model=List[RequestSummaryResponse])
async def get_requests_summary(
    user_email: str = None,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100
) -> List[RequestSummaryResponse]:
    """Get summary list of all requests for a user.

    Args:
        user_email: Optional filter by user email (defaults to current user)
        current_user: Authenticated user email
        db: Database session
        skip: Pagination offset
        limit: Pagination limit

    Returns:
        List of request summaries with counts
    """
    try:
        if not user_email:
            user_email = current_user

        # Build query
        query = select(Request).where(Request.user_email == user_email)
        query = query.order_by(Request.created_date.desc())
        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        requests = result.scalars().all()

        # Build summaries with counts
        summaries = []

        for req in requests:
            # Get certificate counts
            cert_result = await db.execute(
                select(
                    func.count().label('total'),
                    func.sum(
                        func.cast(
                            Certificate.validation_status == 'PASSED',
                            db.bind.dialect.type_descriptor(db.bind.dialect.BIGINT)
                        )
                    ).label('passed'),
                    func.sum(
                        func.cast(
                            Certificate.validation_status == 'FAILED',
                            db.bind.dialect.type_descriptor(db.bind.dialect.BIGINT)
                        )
                    ).label('failed'),
                    func.sum(
                        func.cast(
                            Certificate.validation_status == 'WARNING',
                            db.bind.dialect.type_descriptor(db.bind.dialect.BIGINT)
                        )
                    ).label('warnings')
                ).where(Certificate.request_id == req.id)
            )
            cert_counts = cert_result.one()

            # Get missing certificate count
            missing_result = await db.execute(
                select(func.count()).where(MissingCertificate.request_id == req.id)
            )
            missing_count = missing_result.scalar()

            summaries.append(RequestSummaryResponse(
                id=req.id,
                rfp_number=req.rfp_number,
                bidder_name=req.bidder_name,
                status_code=req.status_code,
                total_certificates=cert_counts.total or 0,
                passed_certificates=cert_counts.passed or 0,
                failed_certificates=cert_counts.failed or 0,
                warning_certificates=cert_counts.warnings or 0,
                missing_certificates_count=missing_count or 0,
                created_date=req.created_date,
                completed_date=req.completed_date,
                user_email=req.user_email
            ))

        logger.info(f"Retrieved {len(summaries)} request summaries for {user_email}")

        return summaries

    except Exception as e:
        logger.error(f"Failed to get request summaries: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve requests: {str(e)}"
        )


@router.get("/{request_id}/details", response_model=RequestDetailedResponse)
async def get_request_details(
    request_id: UUID,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RequestDetailedResponse:
    """Get detailed information about a specific request.

    Args:
        request_id: Request ID
        current_user: Authenticated user email
        db: Database session

    Returns:
        Detailed request information with all related data
    """
    try:
        # Get request
        result = await db.execute(
            select(Request).where(Request.id == request_id)
        )
        request = result.scalar_one_or_none()

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Request not found: {request_id}"
            )

        # Get certificates
        cert_result = await db.execute(
            select(Certificate).where(Certificate.request_id == request_id)
        )
        certificates = [CertificateResponse.model_validate(cert) for cert in cert_result.scalars().all()]

        # Get missing certificates
        missing_result = await db.execute(
            select(MissingCertificate).where(MissingCertificate.request_id == request_id)
        )
        missing_certs = [MissingCertificateResponse.model_validate(mc) for mc in missing_result.scalars().all()]

        # Get other documents
        other_result = await db.execute(
            select(OtherRequiredDocument).where(OtherRequiredDocument.request_id == request_id)
        )
        other_docs = [OtherDocumentResponse.model_validate(od) for od in other_result.scalars().all()]

        # Get notes
        notes_result = await db.execute(
            select(RequestNote).where(RequestNote.request_id == request_id).order_by(RequestNote.created_at.desc())
        )
        notes = [RequestNoteResponse.model_validate(note) for note in notes_result.scalars().all()]

        logger.info(f"Retrieved details for request {request_id}")

        return RequestDetailedResponse(
            id=request.id,
            rfp_number=request.rfp_number,
            bidder_name=request.bidder_name,
            status_code=request.status_code,
            summary=request.summary,
            warning_start_date=request.warning_start_date,
            warning_end_date=request.warning_end_date,
            created_date=request.created_date,
            completed_date=request.completed_date,
            user_email=request.user_email,
            certificates=[cert.model_dump() for cert in certificates],
            missing_certificates=[mc.model_dump() for mc in missing_certs],
            other_documents=[od.model_dump() for od in other_docs],
            notes=[note.model_dump() for note in notes]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get request details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve request details: {str(e)}"
        )


@router.get("/{request_id}/report")
async def get_request_report(
    request_id: UUID,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Get validation report for a request in JSON format.

    Args:
        request_id: Request ID
        current_user: Authenticated user email
        db: Database session

    Returns:
        Complete validation report
    """
    # Get detailed data
    details = await get_request_details(request_id, current_user, db)

    # Format as report
    report = {
        "request_id": str(request_id),
        "rfp_number": details.rfp_number,
        "bidder_name": details.bidder_name,
        "status": details.status_code,
        "created_date": details.created_date.isoformat(),
        "completed_date": details.completed_date.isoformat() if details.completed_date else None,
        "certificates": details.certificates,
        "missing_certificates": details.missing_certificates,
        "other_documents": details.other_documents,
        "validation_summary": details.validation_summary.model_dump() if details.validation_summary else None,
        "notes": details.notes
    }

    return report


@router.get("/{request_id}/missing-certificates", response_model=List[MissingCertificateResponse])
async def get_missing_certificates(
    request_id: UUID,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[MissingCertificateResponse]:
    """Get list of missing certificates for a request.

    Args:
        request_id: Request ID
        current_user: Authenticated user email
        db: Database session

    Returns:
        List of missing certificate types
    """
    try:
        result = await db.execute(
            select(MissingCertificate).where(MissingCertificate.request_id == request_id)
        )
        missing = result.scalars().all()

        return [MissingCertificateResponse.model_validate(m) for m in missing]

    except Exception as e:
        logger.error(f"Failed to get missing certificates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve missing certificates: {str(e)}"
        )


@router.get("/{request_id}/other-documents", response_model=List[OtherDocumentResponse])
async def get_other_documents(
    request_id: UUID,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[OtherDocumentResponse]:
    """Get list of non-certificate documents for a request.

    Args:
        request_id: Request ID
        current_user: Authenticated user email
        db: Database session

    Returns:
        List of other documents (CVs, proposals, etc.)
    """
    try:
        result = await db.execute(
            select(OtherRequiredDocument).where(OtherRequiredDocument.request_id == request_id)
        )
        docs = result.scalars().all()

        return [OtherDocumentResponse.model_validate(d) for d in docs]

    except Exception as e:
        logger.error(f"Failed to get other documents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve other documents: {str(e)}"
        )


@router.post("/{request_id}/notes", response_model=RequestNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_request_note(
    request_id: UUID,
    note_text: str,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> RequestNoteResponse:
    """Add a note to a request.

    Args:
        request_id: Request ID
        note_text: Note content
        current_user: Authenticated user email
        db: Database session

    Returns:
        Created note
    """
    try:
        # Verify request exists
        result = await db.execute(
            select(Request).where(Request.id == request_id)
        )
        request = result.scalar_one_or_none()

        if not request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Request not found: {request_id}"
            )

        # Create note
        note = RequestNote(
            request_id=request_id,
            note=note_text,
            created_by=current_user
        )
        db.add(note)
        await db.commit()
        await db.refresh(note)

        logger.info(f"Added note to request {request_id}")

        return RequestNoteResponse.model_validate(note)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add note: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add note: {str(e)}"
        )
