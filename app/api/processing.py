"""API endpoints for certificate processing workflow."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

from app.config.database import get_db
from app.utils.auth import get_current_user
from app.schemas.request import StartProcessingRequest
from app.models.request import Request
from app.models.attachment import Attachment
from app.models.certificate_type import CertificateType
from app.models.certificate import Certificate
from app.models.missing_certificate import MissingCertificate
from app.models.other_required_document import OtherRequiredDocument
from app.services.ocr import OCRService
from app.services.certificate_extraction import CertificateExtractionService
from app.services.certificate_validation import CertificateValidationService
from app.services.embedding import EmbeddingService
from app.services.file_storage import FileStorageService
from loguru import logger

router = APIRouter(prefix="/api", tags=["processing"])


@router.post("/start-processing")
async def start_processing(
    request_data: StartProcessingRequest,
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Main endpoint to start certificate validation processing.

    This orchestrates the entire workflow:
    1. Create request record
    2. Process each file (OCR)
    3. Extract certificate data with AI
    4. Validate certificates
    5. Generate vector embeddings
    6. Store results
    7. Return summary

    Args:
        request_data: Processing request with files and parameters
        current_user: Authenticated user email
        db: Database session

    Returns:
        Processing result with request ID and validation summary
    """
    try:
        logger.info(
            f"Starting certificate processing for RFP: {request_data.rfp_number}, "
            f"Bidder: {request_data.bidder_name}, User: {current_user}"
        )

        # 1. Create main request record
        new_request = Request(
            id=uuid4(),
            rfp_number=request_data.rfp_number,
            bidder_name=request_data.bidder_name,
            warning_start_date=request_data.warning_start_date,
            warning_end_date=request_data.warning_end_date,
            status_code="PROCESSING",
            user_email=current_user,
            created_by=current_user
        )
        db.add(new_request)
        await db.commit()
        await db.refresh(new_request)

        request_id = new_request.id
        logger.info(f"Created request: {request_id}")

        # 2. Initialize services
        ocr_service = OCRService()
        extraction_service = CertificateExtractionService()
        validation_service = CertificateValidationService()
        embedding_service = EmbeddingService()
        file_storage_service = FileStorageService()

        # 3. Process each file
        all_extractions = []
        full_ocr_text_by_file = {}

        for file_input in request_data.files:
            try:
                logger.info(f"Processing file: {file_input.file_name}")

                # Download file from signed URL
                import httpx
                async with httpx.AsyncClient() as client:
                    file_response = await client.get(file_input.signed_url)
                    file_response.raise_for_status()
                    file_content = file_response.content

                # Create attachment record
                attachment = Attachment(
                    id=file_input.id,
                    request_id=request_id,
                    filename=file_input.file_name,
                    storage_path=file_input.signed_url,  # Already uploaded
                    file_hash="",  # Will be updated
                    file_size=len(file_content),
                    signed_url=file_input.signed_url,
                    document_role=file_input.document_role,
                    created_by=current_user,
                    uploaded_by=current_user
                )
                db.add(attachment)

                # 4. OCR processing
                logger.info(f"Running OCR on {file_input.file_name}")
                ocr_pages = await ocr_service.process_pdf(
                    pdf_content=file_content,
                    filename=file_input.file_name,
                    document_id=str(file_input.id)
                )

                # Combine all page texts for this file
                full_text_pages = [
                    page.get('text', '') for page in ocr_pages
                ]
                full_text = embedding_service.PAGE_DELIMITER.join(full_text_pages)
                full_ocr_text_by_file[str(file_input.id)] = full_text

                # Detect language
                language = ocr_service.detect_language(full_text)

                logger.info(
                    f"OCR completed: {len(ocr_pages)} pages, language: {language}"
                )

                # 5. AI Certificate Extraction
                # --- 3. Extract Certificate Data (Agentic Workflow) ---
                try:
                    from app.agents.extraction_graph import extraction_graph
                    
                    # Invoke LangGraph Agent
                    logger.info(f"Invoking Agentic Extraction for file {file_input.id}")
                    graph_input = {
                        "pages": ocr_pages,
                        "bidder_name": request_data.bidder_name,
                        "certificate_types": [ct.model_dump() for ct in request_data.certificate_types],
                        "rfp_number": request_data.rfp_number,
                        "attempts": 0
                    }
                    
                    agent_output = await extraction_graph.ainvoke(graph_input)
                    result = agent_output.get("extraction_result", {})
                    extractions = [result] if result else []
                    
                    logger.info(f"Agent finished. Attempt count: {agent_output.get('attempts')}")

                except Exception as e:
                    logger.error(f"Agent extraction failed: {e}")
                    raise HTTPException(status_code=500, detail=f"Agent extraction failed: {str(e)}")

                # Attach file_id and request_id to each extraction
                for extraction in extractions:
                    extraction['file_id'] = str(file_input.id)
                    extraction['request_id'] = str(request_id)
                    extraction['language'] = language

                all_extractions.extend(extractions)

                logger.info(
                    f"Extracted {len(extractions)} items from {file_input.file_name}"
                )

            except Exception as e:
                logger.error(f"Failed to process file {file_input.file_name}: {e}")
                # Continue with other files
                continue

        await db.commit()

        # 6. Validate all certificates
        logger.info(f"Validating {len(all_extractions)} extractions")
        validation_result = await validation_service.validate_all_certificates(
            extractions=all_extractions,
            bidder_name=request_data.bidder_name,
            required_certificate_types=request_data.certificate_types,
            warning_start_date=str(request_data.warning_start_date) if request_data.warning_start_date else None,
            warning_end_date=str(request_data.warning_end_date) if request_data.warning_end_date else None
        )

        # 7. Store validated certificates
        for cert_data in validation_result['validated_certificates']:
            certificate = Certificate(
                id=uuid4(),
                request_id=request_id,
                attachment_id=UUID(cert_data['file_id']),
                certificate_type_id=UUID(cert_data['matched_certificate_type_id']) if cert_data.get('matched_certificate_type_id') else None,
                certificate_name=cert_data.get('certificate_type_name'),
                extracted_bidder_name=cert_data.get('extracted_bidder_name'),
                issuer_name=cert_data.get('issuer_name'),
                certificate_number=cert_data.get('certificate_number'),
                issue_date=cert_data.get('issue_date'),
                expiry_date=cert_data.get('expiry_date'),
                validation_status=cert_data['validation_status'],
                validation_issues=cert_data.get('validation_issues', []),
                validation_warnings=cert_data.get('validation_warnings', []),
                created_by=current_user
            )
            db.add(certificate)

        # 8. Store missing certificates
        for missing in validation_result['missing_certificates']:
            missing_cert = MissingCertificate(
                id=uuid4(),
                request_id=request_id,
                certificate_type_id=UUID(missing['certificate_type_id']),
                status="missing",
                created_by=current_user
            )
            db.add(missing_cert)

        # 9. Store non-certificate documents
        for other_doc in validation_result['non_certificate_documents']:
            other_document = OtherRequiredDocument(
                id=uuid4(),
                request_id=request_id,
                attachment_id=UUID(other_doc['file_id']),
                document_type=other_doc.get('document_type'),
                document_name=other_doc.get('certificate_type_name'),
                summary=other_doc.get('extraction_notes'),
                created_by=current_user
            )
            db.add(other_document)

        # 10. Generate and store embeddings
        logger.info("Generating vector embeddings")
        for file_id, full_text in full_ocr_text_by_file.items():
            try:
                await embedding_service.store_certificate_embeddings(
                    db=db,
                    file_id=UUID(file_id),
                    request_id=request_id,
                    full_text=full_text,
                    metadata={
                        'language': ocr_service.detect_language(full_text),
                        'bidder_name': request_data.bidder_name,
                        'rfp_number': request_data.rfp_number
                    }
                )
            except Exception as e:
                logger.error(f"Failed to generate embeddings for file {file_id}: {e}")

        # 11. Update request status
        summary = validation_result['summary']
        new_request.status_code = "COMPLETED" if summary['overall_status'] != "FAILED" else "FAILED"
        new_request.summary = str(summary)
        new_request.completed_date = datetime.utcnow()

        await db.commit()

        logger.info(
            f"Processing completed: Request {request_id}, "
            f"Status: {summary['overall_status']}"
        )

        return {
            "success": True,
            "request_id": str(request_id),
            "status": summary['overall_status'],
            "summary": summary,
            "validated_certificates_count": summary['total_certificates_validated'],
            "missing_certificates_count": summary['missing_certificates_count'],
            "non_certificate_documents_count": summary['non_certificate_documents_count']
        }

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        await db.rollback()

        # Update request status to FAILED if it was created
        if 'new_request' in locals() and new_request.id:
            try:
                new_request.status_code = "FAILED"
                new_request.summary = f"Error: {str(e)}"
                await db.commit()
            except:
                pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Processing failed: {str(e)}"
        )
