import base64
from typing import List, Dict, Any
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.oauth2 import service_account
from loguru import logger

from app.config.settings import settings


class OCRService:
    """Handle OCR processing of PDF documents."""

    def __init__(self) -> None:
        """Initialize OCR service."""
        self.api_url = settings.ocr_api_url
        self.timeout = settings.ocr_timeout
        
        # Initialize Vertex AI
        try:
            # Explicitly load credentials from key file
            credentials = service_account.Credentials.from_service_account_file(
                settings.gcp_service_account_key_path
            )
            
            vertexai.init(
                project=settings.gcp_project_id,
                location=settings.vertex_ai_location,
                credentials=credentials
            )
            logger.info(f"Initialized Vertex AI with project: {settings.gcp_project_id}")
            logger.info(f"Authenticated as Service Account: {credentials.service_account_email}")
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            raise

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
        Process PDF through Gemini Vision and extract text.
        
        Note: Replaces deprecated Azure OCR with robust Gemini Multimodal extraction.
        """
        logger.info(f"Starting Gemini Vision OCR for document: {filename} (ID: {document_id})")

        try:
            # Create Part from PDF bytes
            document_part = Part.from_data(pdf_content, mime_type="application/pdf")
            
            # Prompt for structured extraction
            prompt = """
            You are a high-precision OCR engine. 
            Extract ALL text from this document exactly as it appears. 
            Do not summarize.
            
            IMPORTANT:
            If the document has multiple pages, you MUST enable separation by inserting the exact marker "[[[PAGE_BREAK]]]" between the text of each page.
            Start the output with the text of the first page.
            """
            
            # Generate content
            # Using the model initialized in __init__ or creating a lightweight one here if preferred
            # We use the model defined in settings (default gemini-2.0-flash-exp)
            model = GenerativeModel(settings.vertex_ai_text_model)
            
            response = await model.generate_content_async(
                [document_part, prompt],
                generation_config={"temperature": 0.0}
            )
            
            full_text = response.text
            
            # Split by page marker
            raw_pages = full_text.split("[[[PAGE_BREAK]]]")
            cleaned_pages = [p.strip() for p in raw_pages if p.strip()]
            
            if not cleaned_pages:
                # Fallback if model didn't use split keys properly but returned text
                cleaned_pages = [full_text.strip()]
                
            total_pages = len(cleaned_pages)
            logger.info(f"Gemini OCR completed: {total_pages} pages extracted")

            processed_pages = []
            
            for i, page_text in enumerate(cleaned_pages):
                page_num = i + 1
                
                # Detect language
                language = self.detect_language(page_text)
                word_count = len(page_text.split())
                
                # Add existing marker as downstream expects it
                content_with_marker = f"{page_text}\n\n######End_Of_Page######"
                
                page_data = {
                    "content": content_with_marker,
                    "text": page_text,
                    "metadata": {
                        "documentId": document_id,
                        "fileId": document_id,
                        "fileName": filename,
                        "documentType": document_type,
                        "pageNumber": page_num,
                        "totalPages": total_pages,
                        "language": language,
                        "wordCount": word_count,
                        "timestamp": None,
                        "isLastPage": page_num == total_pages,
                        "fileType": "pdf"
                    }
                }
                
                processed_pages.append(page_data)
                
            return processed_pages

        except Exception as e:
            logger.error(f"Gemini OCR failed: {e}")
            raise RuntimeError(f"OCR processing failed: {e}")
