"""ZIP file extraction and processing service.

Handles ZIP archives containing multiple certificate PDFs.
"""

import io
import zipfile
from typing import List, Dict, Any, Tuple
from uuid import uuid4

from loguru import logger


class ZipHandlerService:
    """Service for extracting and processing ZIP archives."""

    ALLOWED_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg'}
    MAX_FILES_IN_ZIP = 100
    MAX_FILE_SIZE_MB = 50

    @staticmethod
    def is_zip_file(filename: str, content: bytes) -> bool:
        """Check if file is a ZIP archive.

        Args:
            filename: File name
            content: File content bytes

        Returns:
            True if file is a ZIP archive
        """
        # Check by extension
        if filename.lower().endswith('.zip'):
            return True

        # Check by magic number
        if content[:4] == b'PK\x03\x04':
            return True

        return False

    @classmethod
    def extract_files_from_zip(
        cls,
        zip_content: bytes,
        original_filename: str
    ) -> List[Dict[str, Any]]:
        """Extract all supported files from ZIP archive.

        Args:
            zip_content: ZIP file content bytes
            original_filename: Original ZIP filename

        Returns:
            List of extracted file dictionaries with:
            - id: UUID for the file
            - filename: Original filename
            - content: File content bytes
            - size: File size in bytes
            - extension: File extension

        Raises:
            ValueError: If ZIP is invalid or contains too many files
        """
        try:
            extracted_files = []

            with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                # Get list of files (exclude directories)
                file_list = [
                    name for name in zf.namelist()
                    if not name.endswith('/') and not name.startswith('__MACOSX')
                ]

                logger.info(
                    f"ZIP archive '{original_filename}' contains {len(file_list)} files"
                )

                # Check file count limit
                if len(file_list) > cls.MAX_FILES_IN_ZIP:
                    raise ValueError(
                        f"ZIP contains too many files ({len(file_list)}). "
                        f"Maximum allowed: {cls.MAX_FILES_IN_ZIP}"
                    )

                # Extract each file
                for file_info in zf.infolist():
                    # Skip directories and system files
                    if file_info.is_dir() or file_info.filename.startswith('__MACOSX'):
                        continue

                    # Check file extension
                    file_ext = '.' + file_info.filename.rsplit('.', 1)[-1].lower()
                    if file_ext not in cls.ALLOWED_EXTENSIONS:
                        logger.warning(
                            f"Skipping unsupported file: {file_info.filename} "
                            f"(extension: {file_ext})"
                        )
                        continue

                    # Extract file content
                    file_content = zf.read(file_info.filename)
                    file_size_mb = len(file_content) / (1024 * 1024)

                    # Check individual file size
                    if file_size_mb > cls.MAX_FILE_SIZE_MB:
                        logger.warning(
                            f"Skipping large file: {file_info.filename} "
                            f"({file_size_mb:.2f}MB > {cls.MAX_FILE_SIZE_MB}MB)"
                        )
                        continue

                    # Create file record
                    extracted_file = {
                        'id': uuid4(),
                        'filename': file_info.filename,
                        'content': file_content,
                        'size': len(file_content),
                        'extension': file_ext,
                        'from_zip': original_filename
                    }

                    extracted_files.append(extracted_file)
                    logger.debug(
                        f"Extracted: {file_info.filename} ({len(file_content)} bytes)"
                    )

                logger.info(
                    f"Successfully extracted {len(extracted_files)} files from ZIP"
                )

                return extracted_files

        except zipfile.BadZipFile as e:
            logger.error(f"Invalid ZIP file: {e}")
            raise ValueError(f"Invalid ZIP file: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to extract ZIP: {e}")
            raise ValueError(f"Failed to extract ZIP: {str(e)}")

    @classmethod
    def validate_zip_archive(cls, zip_content: bytes) -> Tuple[bool, str]:
        """Validate ZIP archive before processing.

        Args:
            zip_content: ZIP file content bytes

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
                # Test ZIP integrity
                if zf.testzip() is not None:
                    return False, "ZIP archive is corrupted"

                # Count valid files
                file_count = sum(
                    1 for name in zf.namelist()
                    if not name.endswith('/') and not name.startswith('__MACOSX')
                )

                if file_count == 0:
                    return False, "ZIP archive is empty"

                if file_count > cls.MAX_FILES_IN_ZIP:
                    return False, f"ZIP contains too many files ({file_count} > {cls.MAX_FILES_IN_ZIP})"

                return True, ""

        except zipfile.BadZipFile:
            return False, "Invalid ZIP file format"
        except Exception as e:
            return False, f"ZIP validation error: {str(e)}"
