"""Text normalization utilities for OCR cleanup and standardization.

This module handles:
- Arabic digit conversion to Western numerals
- Month name normalization (Arabic & English)
- OCR confusion fixes (O/0, I/l/1)
- Broken numeric pattern repair
- Arabic/English token separation
"""

import re
from typing import Dict, List, Tuple


class TextNormalizer:
    """Normalizes OCR text output for better parsing."""

    # Arabic to Western digit mapping
    ARABIC_DIGITS_MAP = {
        '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
        '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
    }

    # Arabic month names to numbers
    ARABIC_MONTHS = {
        'يناير': '01', 'فبراير': '02', 'مارس': '03', 'أبريل': '04',
        'ابريل': '04', 'مايو': '05', 'يونيو': '06', 'يوليو': '07',
        'أغسطس': '08', 'اغسطس': '08', 'سبتمبر': '09', 'أكتوبر': '10',
        'اكتوبر': '10', 'نوفمبر': '11', 'ديسمبر': '12'
    }

    # English month names to numbers
    ENGLISH_MONTHS = {
        'january': '01', 'jan': '01',
        'february': '02', 'feb': '02',
        'march': '03', 'mar': '03',
        'april': '04', 'apr': '04',
        'may': '05',
        'june': '06', 'jun': '06',
        'july': '07', 'jul': '07',
        'august': '08', 'aug': '08',
        'september': '09', 'sep': '09', 'sept': '09',
        'october': '10', 'oct': '10',
        'november': '11', 'nov': '11',
        'december': '12', 'dec': '12'
    }

    @classmethod
    def convert_arabic_digits(cls, text: str) -> str:
        """Convert Arabic-Indic digits (٠-٩) to Western digits (0-9).

        Args:
            text: Input text with potential Arabic digits

        Returns:
            Text with all Arabic digits converted to Western
        """
        for arabic, western in cls.ARABIC_DIGITS_MAP.items():
            text = text.replace(arabic, western)
        return text

    @classmethod
    def normalize_month_names(cls, text: str) -> str:
        """Convert month names (Arabic & English) to numeric format.

        Args:
            text: Input text with potential month names

        Returns:
            Text with month names replaced by numbers (01-12)
        """
        # Normalize Arabic months
        for month_name, month_num in cls.ARABIC_MONTHS.items():
            text = re.sub(
                r'\b' + re.escape(month_name) + r'\b',
                month_num,
                text,
                flags=re.IGNORECASE
            )

        # Normalize English months
        for month_name, month_num in cls.ENGLISH_MONTHS.items():
            text = re.sub(
                r'\b' + re.escape(month_name) + r'\b',
                month_num,
                text,
                flags=re.IGNORECASE
            )

        return text

    @classmethod
    def fix_ocr_confusions(cls, text: str) -> str:
        """Fix common OCR character confusions in numeric contexts.

        Fixes:
        - Letter O → digit 0 when surrounded by digits
        - Letter I/l → digit 1 when in numeric context

        Args:
            text: Input text with potential OCR errors

        Returns:
            Text with OCR confusions corrected
        """
        # Fix O → 0 in numeric contexts
        # Match patterns like "2O21" or "1O" or "O5"
        text = re.sub(r'(\d)O(\d)', r'\g<1>0\g<2>', text)  # Between digits
        text = re.sub(r'(\d)O\b', r'\g<1>0', text)  # After digit, word boundary
        text = re.sub(r'\bO(\d)', r'0\g<1>', text)  # Before digit, word boundary

        # Fix I/l → 1 in numeric contexts
        text = re.sub(r'(\d)[Il](\d)', r'\g<1>1\g<2>', text)  # Between digits
        text = re.sub(r'(\d)[Il]\b', r'\g<1>1', text)  # After digit
        text = re.sub(r'\b[Il](\d)', r'1\g<1>', text)  # Before digit

        return text

    @classmethod
    def repair_broken_numerics(cls, text: str) -> str:
        """Repair broken numeric patterns where digits are separated by spaces.

        Examples:
        - "2 0 2 1" → "2021"
        - "1 5 / 0 3 / 2 0 2 4" → "15/03/2024"
        - "Valid until 3 1 - 1 2 - 2 0 2 5" → "Valid until 31-12-2025"

        Args:
            text: Input text with broken numeric patterns

        Returns:
            Text with repaired numeric sequences
        """
        # Pattern: digit + space + digit (potentially repeating)
        # But preserve word boundaries

        # Fix date-like patterns: "d d / d d / d d d d" or "d d - d d - d d d d"
        text = re.sub(
            r'(\d)\s+(\d)\s*/\s*(\d)\s+(\d)\s*/\s*(\d)\s+(\d)\s+(\d)\s+(\d)',
            r'\1\2/\3\4/\5\6\7\8',
            text
        )
        text = re.sub(
            r'(\d)\s+(\d)\s*-\s*(\d)\s+(\d)\s*-\s*(\d)\s+(\d)\s+(\d)\s+(\d)',
            r'\1\2-\3\4-\5\6\7\8',
            text
        )

        # Fix 4-digit years: "2 0 2 1" → "2021"
        text = re.sub(r'(\d)\s+(\d)\s+(\d)\s+(\d)(?!\s*\d)', r'\1\2\3\4', text)

        # Fix 2-digit patterns: "1 5" → "15" (but only in numeric contexts)
        text = re.sub(r'(?<=[\d/\-])\s*(\d)\s+(\d)\s*(?=[\d/\-])', r'\1\2', text)

        # General: remove spaces between consecutive single digits (max 4 iterations)
        for _ in range(4):
            text = re.sub(r'(\d)\s+(\d)', r'\1\2', text)

        return text

    @classmethod
    def separate_tokens(cls, text: str) -> str:
        """Separate Arabic and English tokens for better parsing.

        Ensures proper spacing between:
        - Arabic text and English text
        - Text and numbers
        - Different scripts

        Args:
            text: Input text with mixed scripts

        Returns:
            Text with proper token separation
        """
        # Add space between Arabic and Latin characters
        # Arabic Unicode range: \u0600-\u06FF
        text = re.sub(r'([\u0600-\u06FF])([a-zA-Z0-9])', r'\1 \2', text)
        text = re.sub(r'([a-zA-Z0-9])([\u0600-\u06FF])', r'\1 \2', text)

        # Normalize multiple spaces to single space
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    @classmethod
    def normalize_whitespace(cls, text: str) -> str:
        """Normalize all whitespace to single spaces.

        Args:
            text: Input text with irregular whitespace

        Returns:
            Text with normalized whitespace
        """
        # Replace all whitespace chars (including tabs, newlines) with space
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @classmethod
    def add_newline_markers(cls, text: str) -> str:
        """Replace newlines with [[NL]] markers for LLM processing.

        This matches the n8n workflow logic where newlines are replaced
        with logical markers to help the LLM understand text structure.

        Args:
            text: Text with newlines

        Returns:
            Text with [[NL]] markers instead of newlines
        """
        # Clean up excessive newlines first
        text = re.sub(r'\n{2,}', '\n', text)
        # Replace newlines with marker
        text = text.replace('\n', ' [[NL]] ')
        # Clean up excessive spaces
        text = re.sub(r'\s{2,}', ' ', text)
        return text.strip()

    @classmethod
    def apply_ocr_confusion_fixes(cls, text: str) -> str:
        """Apply OCR-specific confusion fixes from n8n workflow.

        Fixes from the n8n "Normalize OCR Text" node:
        - O/o → 0 (in all contexts)
        - l/I → 1 (in all contexts)
        - Em dash/en dash → hyphen
        - Colon/dot/bullet → slash (for dates)
        - Arabic decimal separators → dots

        Args:
            text: Input text with OCR errors

        Returns:
            Text with OCR confusions fixed
        """
        # Fix letter O/o → digit 0
        text = text.replace('O', '0').replace('o', '0')

        # Fix letter I/l → digit 1
        text = text.replace('I', '1').replace('l', '1')

        # Fix dashes
        text = text.replace('—', '-').replace('–', '-')

        # Fix colon/dot/bullet in dates
        text = text.replace(':', '/').replace('·', '/').replace('•', '/')

        # Fix Arabic decimal separators (Arabic comma/thousands separator → dot)
        text = text.replace('\u066B', '.').replace('\u066C', '.')

        return text

    @classmethod
    def normalize_full_text(cls, text: str) -> str:
        """Apply all normalization steps to the input text.

        This is the main entry point for text normalization.
        Applies transformations in the optimal order:
        1. Convert Arabic digits
        2. Normalize month names
        3. Fix OCR confusions
        4. Repair broken numerics
        5. Separate tokens
        6. Normalize whitespace

        Args:
            text: Raw OCR text output

        Returns:
            Fully normalized text ready for parsing
        """
        if not text:
            return ""

        # Apply all transformations in sequence (EXACT n8n order)
        # 1️⃣ Fix OCR confusions FIRST
        text = cls.apply_ocr_confusion_fixes(text)

        # 2️⃣ Convert Arabic digits → Western
        text = cls.convert_arabic_digits(text)

        # 3️⃣ Normalize month names
        text = cls.normalize_month_names(text)

        # 4️⃣ Repair broken numeric patterns
        text = cls.repair_broken_numerics(text)

        # 5️⃣ Separate Arabic and English tokens
        text = cls.separate_tokens(text)

        # 6️⃣ Clean up punctuation spacing & newlines
        text = text.replace('\u066B', '.').replace('\u066C', '.')
        text = re.sub(r'\s{2,}', ' ', text)
        text = re.sub(r'\n{2,}', '\n', text)
        text = text.strip()

        # 7️⃣ Replace newlines with [[NL]] markers for LLM
        text = cls.add_newline_markers(text)

        # 8️⃣ Final tidy-up
        text = re.sub(r'\s{2,}', ' ', text).strip()

        return text

    @classmethod
    def normalize_ocr_pages(cls, pages: List[Dict]) -> List[Dict]:
        """Normalize OCR output for multiple pages.

        Args:
            pages: List of page dictionaries with 'text' field

        Returns:
            List of pages with normalized text
        """
        normalized_pages = []

        for page in pages:
            normalized_page = page.copy()
            if 'text' in page and page['text']:
                normalized_page['text'] = cls.normalize_full_text(page['text'])
            normalized_pages.append(normalized_page)

        return normalized_pages

    @classmethod
    def extract_dates(cls, text: str) -> List[str]:
        """Extract potential date patterns from normalized text.

        Looks for common date formats:
        - DD/MM/YYYY
        - DD-MM-YYYY
        - YYYY/MM/DD
        - YYYY-MM-DD

        Args:
            text: Normalized text

        Returns:
            List of date strings found in the text
        """
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b',  # DD/MM/YYYY or DD-MM-YYYY
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',  # YYYY/MM/DD or YYYY-MM-DD
        ]

        dates = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            dates.extend(matches)

        return dates


# Convenience function for quick access
def normalize_text(text: str) -> str:
    """Quick normalization function.

    Args:
        text: Raw OCR text

    Returns:
        Normalized text
    """
    return TextNormalizer.normalize_full_text(text)
