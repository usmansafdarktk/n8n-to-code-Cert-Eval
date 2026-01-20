"""OCR service for extracting text from PDF documents."""
import base64
from typing import List, Dict, Any
import httpx
from loguru import logger

from app.config.settings import settings


class OCRService:
    """Handle OCR processing of PDF documents."""

    def __init__(self) -> None:
        """Initialize OCR service."""
        self.api_url = settings.ocr_api_url
        self.timeout = settings.ocr_timeout

    def detect_language(self, text: str) -> str:
        """
        Detect document language from text sample.

        Args:
            text: Text sample (first 500 chars)

        Returns:
            Language code: 'ar', 'en', 'bilingual', or 'unknown'
        """
        sample = text[:500]
        arabic_chars = sum(1 for c in sample if '\u0600' <= c <= '\u06FF')
        latin_chars = sum(1 for c in sample if c.isalpha() and c.isascii())

        if arabic_chars > latin_chars * 2:
            return "ar"
        elif latin_chars > arabic_chars * 2:
            return "en"
        elif arabic_chars and latin_chars:
            return "bilingual"
        return "unknown"

    async def process_pdf(
        self,
        pdf_content: bytes,
        filename: str,
        document_id: str,
        document_type: str = "certificate"
    ) -> List[Dict[str, Any]]:
        """
        Process PDF through OCR API and extract text per page.

        Args:
            pdf_content: PDF file bytes
            filename: Original filename
            document_id: Document UUID
            document_type: Type of document

        Returns:
            List of page data with text and metadata
        """
        logger.info(f"Starting OCR for document: {filename} (ID: {document_id})")

        # Encode PDF to base64
        pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

        # Prepare request payload
        payload = {
            "Name": filename,
            "StringBase64Content": pdf_base64,
            "BinaryContent": None
        }

        # Call OCR API
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                ocr_result = response.json()

            except httpx.HTTPError as e:
                logger.error(f"OCR API request failed: {e}")
                raise RuntimeError(f"OCR processing failed: {e}")

        # Parse OCR response
        if isinstance(ocr_result, list):
            ocr_data = ocr_result[0].get("result", [{}])[0]
        elif isinstance(ocr_result, dict):
            result = ocr_result.get("result", [])
            ocr_data = result[0] if isinstance(result, list) else result
        else:
            raise ValueError("Unexpected OCR response format")

        pages = ocr_data.get("pages", [])
        total_pages = ocr_data.get("totalPages", len(pages))

        logger.info(f"OCR completed: {total_pages} pages extracted from {filename}")

        # Process each page
        processed_pages = []
        timestamp = None

        for page_index, page_content in enumerate(pages):
            # Clean page text
            page_text = page_content.replace('\r\n', '\n').replace('\n\n\n', '\n\n').strip()

            # Detect language
            language = self.detect_language(page_text)

            # Word count
            word_count = len(page_text.split())

            # Add page marker
            content_with_marker = f"{page_text}\n\n######End_Of_Page######"

            page_data = {
                "content": content_with_marker,
                "text": page_text,
                "metadata": {
                    "documentId": document_id,
                    "fileId": document_id,
                    "fileName": filename,
                    "documentType": document_type,
                    "pageNumber": page_index + 1,
                    "totalPages": total_pages,
                    "language": language,
                    "wordCount": word_count,
                    "timestamp": timestamp,
                    "isLastPage": (page_index + 1) == total_pages,
                    "fileType": "pdf"
                }
            }

            processed_pages.append(page_data)

        return processed_pages
