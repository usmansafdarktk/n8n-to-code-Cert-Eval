"""Google Cloud Storage service for file operations."""
import hashlib
from datetime import datetime, timedelta
from typing import Tuple, Optional
from google.cloud import storage
from google.auth import compute_engine
from loguru import logger

from app.config.settings import settings


class FileStorageService:
    """Handle file uploads and signed URL generation with Google Cloud Storage."""

    def __init__(self) -> None:
        """Initialize GCS client with local fallback."""
        try:
            self.client = storage.Client.from_service_account_json(
                settings.gcp_service_account_key_path
            )
            self.bucket = self.client.bucket(settings.gcs_bucket_name)
            self.is_local = False
        except Exception as e:
            logger.warning(f"GCS init failed ({e}), falling back to local storage")
            self.is_local = True
            # Create local upload dir
            import os
            self.local_dir = "static/uploads"
            os.makedirs(self.local_dir, exist_ok=True)

    def calculate_file_hash(self, file_content: bytes) -> str:
        """
        Calculate SHA256 hash of file content.

        Args:
            file_content: File bytes

        Returns:
            SHA256 hash string
        """
        return hashlib.sha256(file_content).hexdigest()

    def transliterate_arabic_filename(self, filename: str) -> Tuple[str, bool]:
        """
        Transliterate Arabic characters in filename to English.

        Args:
            filename: Original filename

        Returns:
            Tuple of (converted_filename, was_arabic)
        """
        arabic_to_english = {
            'ا': 'a', 'أ': 'a', 'إ': 'e', 'آ': 'aa', 'ء': '',
            'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'h',
            'خ': 'kh', 'د': 'd', 'ذ': 'th', 'ر': 'r', 'ز': 'z',
            'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't',
            'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f', 'ق': 'q',
            'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ه': 'h',
            'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 'h', 'ئ': 'e',
            'ؤ': 'o', ' ': '_', '٠': '0', '١': '1', '٢': '2',
            '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7',
            '٨': '8', '٩': '9',
        }

        # Check if contains Arabic
        has_arabic = any('\u0600' <= char <= '\u06FF' for char in filename)

        if not has_arabic:
            return filename, False

        # Split name and extension
        parts = filename.rsplit('.', 1)
        name = parts[0]
        ext = f".{parts[1]}" if len(parts) > 1 else ""

        # Transliterate
        converted = ''.join(arabic_to_english.get(char, char) for char in name)
        converted = converted.replace('_', ' ').replace('  ', ' ').strip().replace(' ', '_')

        logger.info(f"Transliterated filename: {filename} -> {converted}{ext}")
        return f"{converted}{ext}", True

    async def upload_file(
        self,
        file_content: bytes,
        filename: str,
        content_type: str = "application/pdf"
    ) -> Tuple[str, str, str]:
        """
        Upload file to GCS and generate signed URL.

        Args:
            file_content: File bytes
            filename: Original filename
            content_type: MIME type

        Returns:
            Tuple of (storage_path, signed_url, file_hash)
        """
        # Transliterate Arabic filename
        clean_filename, was_arabic = self.transliterate_arabic_filename(filename)

        # Add timestamp to filename
        timestamp = datetime.utcnow().strftime("%d_%m_%y_%H%M%S")
        clean_filename = clean_filename.replace('.pdf', f'_{timestamp}.pdf')

        # Build storage path
        storage_path = f"{settings.gcs_bucket_folder}/{clean_filename}"

        # Calculate hash
        file_hash = self.calculate_file_hash(file_content)

        if not self.is_local:
            # GCS Upload
            blob = self.bucket.blob(storage_path)
            blob.upload_from_string(file_content, content_type=content_type)
            logger.info(f"Uploaded to GCS: {storage_path}")
            # Generate signed URL
            signed_url = await self.generate_signed_url(storage_path)
        else:
            # Local Save (only if explicitly configured as local in init)
            save_path = f"{self.local_dir}/{clean_filename}"
            with open(save_path, "wb") as f:
                f.write(file_content)
            
            storage_path = save_path
            signed_url = f"http://localhost:8000/{save_path}"
            logger.info(f"Saved locally: {storage_path}")

        return storage_path, signed_url, file_hash

    async def generate_signed_url(
        self,
        storage_path: str,
        expiration_days: Optional[int] = None
    ) -> str:
        """
        Generate a signed URL for accessing file.

        Args:
            storage_path: Path in GCS bucket
            expiration_days: Days until URL expires (default from settings)

        Returns:
            Signed URL string
        """
        if expiration_days is None:
            expiration_days = settings.signed_url_expiration_days

        expiration = datetime.utcnow() + timedelta(days=expiration_days)

        if self.is_local:
            return f"http://localhost:8000/{storage_path}"

        blob = self.bucket.blob(storage_path)

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET",
            service_account_email=settings.gcp_service_account_email,
        )

        logger.debug(f"Generated signed URL for {storage_path}, expires: {expiration}")

        return signed_url

    async def check_url_expiration(
        self,
        signed_url: Optional[str],
        expiration_date: Optional[datetime]
    ) -> bool:
        """
        Check if signed URL is still valid.

        Args:
            signed_url: Current signed URL
            expiration_date: Expiration timestamp

        Returns:
            True if URL is valid, False if expired or missing
        """
        if not signed_url or not expiration_date:
            return False

        return datetime.utcnow() < expiration_date
