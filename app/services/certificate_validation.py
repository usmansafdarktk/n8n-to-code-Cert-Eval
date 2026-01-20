"""Certificate validation service with comprehensive business rules.

This service implements all validation logic from the original n8n workflow,
including expiry checks, bidder name matching, certificate type validation,
and missing certificate detection.
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from uuid import UUID

from loguru import logger


class CertificateValidationService:
    """Service for validating extracted certificates against business rules."""

    # Validation issue types
    ISSUE_EXPIRY_REQUIRED = "EXPIRY_REQUIRED"
    ISSUE_CERTIFICATE_EXPIRED = "CERTIFICATE_EXPIRED"
    ISSUE_EXPIRY_IN_WARNING = "EXPIRY_IN_WARNING_PERIOD"
    ISSUE_DATE_ORDER = "INVALID_DATE_ORDER"
    ISSUE_BIDDER_MISMATCH = "BIDDER_NAME_MISMATCH"
    ISSUE_TYPE_NOT_MATCHED = "CERTIFICATE_TYPE_NOT_MATCHED"

    # Validation statuses
    STATUS_PASSED = "PASSED"
    STATUS_WARNING = "WARNING"
    STATUS_FAILED = "FAILED"

    def __init__(self):
        """Initialize the validation service."""
        pass

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime object.

        Args:
            date_str: Date string in ISO format (YYYY-MM-DD)

        Returns:
            datetime object or None if parsing fails
        """
        if not date_str:
            return None

        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return None

    def _deduplicate_certificates(
        self,
        extractions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate certificates based on file_id + page_number.

        Args:
            extractions: List of extraction results

        Returns:
            Deduplicated list of certificates
        """
        seen = set()
        deduplicated = []

        for extraction in extractions:
            # Only process actual certificates
            if not extraction.get('is_certificate'):
                continue

            file_id = extraction.get('file_id')
            page_number = extraction.get('page_number')

            key = (file_id, page_number)

            if key not in seen:
                seen.add(key)
                deduplicated.append(extraction)
            else:
                logger.debug(
                    f"Duplicate certificate detected: file_id={file_id}, "
                    f"page={page_number}"
                )

        logger.info(
            f"Deduplicated {len(extractions)} extractions to "
            f"{len(deduplicated)} unique certificates"
        )

        return deduplicated

    def validate_single_certificate(
        self,
        extraction: Dict[str, Any],
        bidder_name: str,
        warning_start_date: Optional[datetime],
        warning_end_date: Optional[datetime]
    ) -> Dict[str, Any]:
        """Validate a single certificate against all business rules.

        Args:
            extraction: Certificate extraction result
            bidder_name: Official bidder name to match against
            warning_start_date: Start of warning period for expiry
            warning_end_date: End of warning period for expiry

        Returns:
            Dictionary with validation results including issues and warnings
        """
        issues = []
        warnings = []
        validation_status = self.STATUS_PASSED

        # Get extracted data
        has_expiry = extraction.get('has_expiry', True)
        issue_date_str = extraction.get('issue_date')
        expiry_date_str = extraction.get('expiry_date')
        bidder_match_confidence = extraction.get('bidder_name_match_confidence')
        cert_type_match_confidence = extraction.get('certificate_type_match_confidence')

        # Parse dates
        issue_date = self._parse_date(issue_date_str)
        expiry_date = self._parse_date(expiry_date_str)
        current_date = datetime.now()

        # Rule 1: EXPIRY_REQUIRED
        # If certificate type requires expiry but none found
        if has_expiry and not expiry_date:
            issues.append({
                "type": self.ISSUE_EXPIRY_REQUIRED,
                "severity": "ERROR",
                "message": "Certificate requires an expiry date but none was found",
                "details": {
                    "has_expiry_requirement": has_expiry,
                    "expiry_date_found": False
                }
            })
            validation_status = self.STATUS_FAILED

        # Rule 2: CERTIFICATE_EXPIRED
        # Check if certificate has expired
        if expiry_date and expiry_date < current_date:
            issues.append({
                "type": self.ISSUE_CERTIFICATE_EXPIRED,
                "severity": "ERROR",
                "message": f"Certificate expired on {expiry_date.strftime('%Y-%m-%d')}",
                "details": {
                    "expiry_date": expiry_date_str,
                    "current_date": current_date.strftime('%Y-%m-%d'),
                    "days_expired": (current_date - expiry_date).days
                }
            })
            validation_status = self.STATUS_FAILED

        # Rule 3: EXPIRY_IN_WARNING_PERIOD
        # Check if expiry falls within warning period
        if (expiry_date and
            warning_start_date and warning_end_date and
            validation_status != self.STATUS_FAILED):  # Only if not already failed

            if warning_start_date <= expiry_date <= warning_end_date:
                warnings.append({
                    "type": self.ISSUE_EXPIRY_IN_WARNING,
                    "severity": "WARNING",
                    "message": (
                        f"Certificate will expire soon on {expiry_date.strftime('%Y-%m-%d')}, "
                        f"which falls within the warning period"
                    ),
                    "details": {
                        "expiry_date": expiry_date_str,
                        "warning_start": warning_start_date.strftime('%Y-%m-%d'),
                        "warning_end": warning_end_date.strftime('%Y-%m-%d'),
                        "days_until_expiry": (expiry_date - current_date).days
                    }
                })

                # Only set to WARNING if not already FAILED
                if validation_status == self.STATUS_PASSED:
                    validation_status = self.STATUS_WARNING

        # Rule 4: INVALID_DATE_ORDER
        # Issue date should be before expiry date
        if issue_date and expiry_date and issue_date >= expiry_date:
            issues.append({
                "type": self.ISSUE_DATE_ORDER,
                "severity": "ERROR",
                "message": "Issue date is not before expiry date",
                "details": {
                    "issue_date": issue_date_str,
                    "expiry_date": expiry_date_str
                }
            })
            validation_status = self.STATUS_FAILED

        # Rule 5: BIDDER_NAME_MISMATCH
        # Check bidder name matching confidence
        if bidder_match_confidence in ['LOW', 'NONE']:
            issues.append({
                "type": self.ISSUE_BIDDER_MISMATCH,
                "severity": "ERROR",
                "message": (
                    f"Bidder name on certificate does not match expected name "
                    f"(confidence: {bidder_match_confidence})"
                ),
                "details": {
                    "expected_bidder_name": bidder_name,
                    "extracted_bidder_name": extraction.get('extracted_bidder_name'),
                    "match_confidence": bidder_match_confidence
                }
            })
            validation_status = self.STATUS_FAILED

        elif bidder_match_confidence == 'MEDIUM':
            warnings.append({
                "type": self.ISSUE_BIDDER_MISMATCH,
                "severity": "WARNING",
                "message": (
                    "Bidder name on certificate has medium confidence match "
                    "with expected name"
                ),
                "details": {
                    "expected_bidder_name": bidder_name,
                    "extracted_bidder_name": extraction.get('extracted_bidder_name'),
                    "match_confidence": bidder_match_confidence
                }
            })

            if validation_status == self.STATUS_PASSED:
                validation_status = self.STATUS_WARNING

        # Rule 6: CERTIFICATE_TYPE_NOT_MATCHED
        # Check if certificate type was matched to valid types
        if cert_type_match_confidence in ['LOW', 'NONE']:
            issues.append({
                "type": self.ISSUE_TYPE_NOT_MATCHED,
                "severity": "ERROR",
                "message": (
                    f"Certificate type could not be matched to required types "
                    f"(confidence: {cert_type_match_confidence})"
                ),
                "details": {
                    "extracted_type": extraction.get('certificate_type_name'),
                    "matched_type_id": extraction.get('matched_certificate_type_id'),
                    "match_confidence": cert_type_match_confidence
                }
            })
            validation_status = self.STATUS_FAILED

        elif cert_type_match_confidence == 'MEDIUM':
            warnings.append({
                "type": self.ISSUE_TYPE_NOT_MATCHED,
                "severity": "WARNING",
                "message": (
                    "Certificate type has medium confidence match with required types"
                ),
                "details": {
                    "extracted_type": extraction.get('certificate_type_name'),
                    "matched_type_id": extraction.get('matched_certificate_type_id'),
                    "match_confidence": cert_type_match_confidence
                }
            })

            if validation_status == self.STATUS_PASSED:
                validation_status = self.STATUS_WARNING

        return {
            "validation_status": validation_status,
            "validation_issues": issues,
            "validation_warnings": warnings,
            "issue_count": len(issues),
            "warning_count": len(warnings)
        }

    def find_missing_certificates(
        self,
        validated_certificates: List[Dict[str, Any]],
        required_certificate_types: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify which required certificate types are missing.

        Args:
            validated_certificates: List of validated certificates
            required_certificate_types: List of all required certificate types

        Returns:
            List of missing certificate type information
        """
        # Collect all matched certificate type IDs from validated certificates
        matched_type_ids = set()

        for cert in validated_certificates:
            # Only count PASSED or WARNING certificates
            if cert.get('validation_status') in [self.STATUS_PASSED, self.STATUS_WARNING]:
                matched_id = cert.get('matched_certificate_type_id')
                if matched_id:
                    matched_type_ids.add(str(matched_id))

        # Find missing types
        missing_types = []

        for cert_type in required_certificate_types:
            cert_type_id = str(cert_type.get('id'))

            if cert_type_id not in matched_type_ids:
                missing_types.append({
                    "certificate_type_id": cert_type_id,
                    "certificate_type_name_en": cert_type.get('name_en'),
                    "certificate_type_name_ar": cert_type.get('name_ar'),
                    "is_required": cert_type.get('is_required', True)
                })

        logger.info(
            f"Missing certificates: {len(missing_types)} out of "
            f"{len(required_certificate_types)} required types"
        )

        return missing_types

    def generate_validation_summary(
        self,
        validated_certificates: List[Dict[str, Any]],
        missing_certificates: List[Dict[str, Any]],
        non_certificate_documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate overall validation summary.

        Args:
            validated_certificates: List of validated certificates
            missing_certificates: List of missing certificate types
            non_certificate_documents: List of non-certificate documents

        Returns:
            Summary dictionary with counts and overall status
        """
        total_certificates = len(validated_certificates)
        passed_count = sum(
            1 for c in validated_certificates
            if c.get('validation_status') == self.STATUS_PASSED
        )
        warning_count = sum(
            1 for c in validated_certificates
            if c.get('validation_status') == self.STATUS_WARNING
        )
        failed_count = sum(
            1 for c in validated_certificates
            if c.get('validation_status') == self.STATUS_FAILED
        )

        total_issues = sum(c.get('issue_count', 0) for c in validated_certificates)
        total_warnings = sum(c.get('warning_count', 0) for c in validated_certificates)

        # Overall status determination
        if failed_count > 0 or len(missing_certificates) > 0:
            overall_status = self.STATUS_FAILED
        elif warning_count > 0:
            overall_status = self.STATUS_WARNING
        else:
            overall_status = self.STATUS_PASSED

        summary = {
            "overall_status": overall_status,
            "total_certificates_validated": total_certificates,
            "certificates_passed": passed_count,
            "certificates_with_warnings": warning_count,
            "certificates_failed": failed_count,
            "total_issues": total_issues,
            "total_warnings": total_warnings,
            "missing_certificates_count": len(missing_certificates),
            "non_certificate_documents_count": len(non_certificate_documents),
            "validation_timestamp": datetime.now().isoformat()
        }

        logger.info(
            f"Validation summary: {overall_status} | "
            f"Passed: {passed_count}, Warnings: {warning_count}, "
            f"Failed: {failed_count}, Missing: {len(missing_certificates)}"
        )

        return summary

    async def validate_all_certificates(
        self,
        extractions: List[Dict[str, Any]],
        bidder_name: str,
        required_certificate_types: List[Dict[str, Any]],
        warning_start_date: Optional[str] = None,
        warning_end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Main validation workflow for all extracted documents.

        Args:
            extractions: List of all extraction results from AI service
            bidder_name: Official bidder name
            required_certificate_types: List of required certificate types
            warning_start_date: Start of warning period (ISO format)
            warning_end_date: End of warning period (ISO format)

        Returns:
            Complete validation result with certificates, missing types, and summary
        """
        # Parse warning dates
        warning_start = self._parse_date(warning_start_date)
        warning_end = self._parse_date(warning_end_date)

        # Separate certificates from non-certificates
        certificates = [e for e in extractions if e.get('is_certificate')]
        non_certificates = [e for e in extractions if not e.get('is_certificate')]

        logger.info(
            f"Processing {len(extractions)} extractions: "
            f"{len(certificates)} certificates, {len(non_certificates)} non-certificates"
        )

        # Deduplicate certificates
        unique_certificates = self._deduplicate_certificates(certificates)

        # Validate each certificate
        validated_certificates = []

        for cert in unique_certificates:
            validation_result = self.validate_single_certificate(
                extraction=cert,
                bidder_name=bidder_name,
                warning_start_date=warning_start,
                warning_end_date=warning_end
            )

            # Merge validation results into certificate data
            validated_cert = {**cert, **validation_result}
            validated_certificates.append(validated_cert)

        # Find missing certificates
        missing_certificates = self.find_missing_certificates(
            validated_certificates=validated_certificates,
            required_certificate_types=required_certificate_types
        )

        # Generate summary
        summary = self.generate_validation_summary(
            validated_certificates=validated_certificates,
            missing_certificates=missing_certificates,
            non_certificate_documents=non_certificates
        )

        return {
            "validated_certificates": validated_certificates,
            "missing_certificates": missing_certificates,
            "non_certificate_documents": non_certificates,
            "summary": summary
        }
