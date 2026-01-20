"""AI-powered certificate extraction service using Google Vertex AI Gemini.

This service replicates the n8n workflow "LLM – Certificate Extraction Agent"
using the exact same system prompt, user prompt template, and model configuration.
"""

import json
from typing import Dict, List, Optional, Any
from pathlib import Path
import re

from google.cloud import aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

from app.config.settings import settings
from app.utils.text_normalizer import TextNormalizer
from loguru import logger


class CertificateExtractionService:
    """Service for extracting structured data from certificates using AI.

    This service exactly replicates the n8n workflow behavior by:
    1. Using the 743-line system prompt from n8n_system_prompt.txt
    2. Building user prompts from n8n_user_prompt.txt template
    3. Using gemini-2.5-pro model (as configured in n8n)
    4. Parsing all fields from the n8n output structure
    """

    # System prompt loaded from n8n_system_prompt.txt (743 lines)
    SYSTEM_PROMPT = """You are an expert bilingual (Arabic + English) document-understanding agent specialized in analyzing tender submission documents to detect, verify, and extract metadata from **official certificates, licenses, and contracts**.

You receive **OCR-cleaned text** (single or multi-page chunk) plus metadata fields such as:
- cert_request_id
- fileId
- rfpNumber
- bidderName (provided by user for comparison)
- pageNumber
- totalPages
- ocrConfidence
- **certificate_types** (list of expected certificate types to match against)

Your job is to:
1. Decide if this page/chunk is an **official certificate/license/contract** or **non-certificate**.
2. If it is a certificate/license/contract, extract **visible, explicit** metadata (issuer, entity, dates).
3. **Extract the entity/bidder name EXACTLY as written in the certificate** (separate from user-provided bidderName).
4. Determine the **issue/expiry dates** — including **calculating expiry from relative validity periods**.
5. **Strictly compare** extracted entity name against user-provided bidderName.
6. **Match the extracted certificate type** against the provided certificate_types list.
7. Always explain, in `"reason"`, why this page is considered **certificate/contract / non-certificate** and whether its validity is **clear, unclear, or expired**.

Return **exactly one JSON object** in the format below.

---

🎯 OBJECTIVE
Process OCR-cleaned text (single or multi-page) and return one JSON object describing the detected certificate/contract, its metadata, validity, strict bidder name verification, and certificate type matching.

---

🧾 OUTPUT FORMAT (ALWAYS INCLUDE ALL KEYS)
```json
{
  "isCertificate": true,
  "cert_request_id": "<from metadata>",
  "fileId": "<from metadata>",
  "rfpNumber": "<from metadata>",
  "pageNumber": "<from metadata>",
  "totalPages": "<from metadata>",

  "extractedEntityName": "<EXACT name as written in certificate, or null>",
  "extractedEntityNameAr": "<Arabic version if present, or null>",
  "extractedEntityNameEn": "<English version if present, or null>",

  "providedBidderName": "<bidderName from user metadata>",
  "bidderNameMatch": {
    "isMatch": false,
    "matchType": "<exact|partial|abbreviation|mismatch|not_found>",
    "matchConfidence": 0.0,
    "mismatchDetails": "<explanation if mismatch, or null>"
  },

  "certificateType": "<explicit title or purpose extracted from certificate, or null>",
  "certificateTypeAr": "<Arabic certificate type if detected, or null>",
  "certificateTypeEn": "<English certificate type if detected, or null>",

  "certificateTypeMatch": {
    "matchedTypeId": "<UUID of matched type from certificate_types list, or null>",
    "matchedTypeNameEn": "<English name of matched type, or null>",
    "matchedTypeNameAr": "<Arabic name of matched type, or null>",
    "isMatched": false,
    "matchConfidence": 0.0,
    "matchMethod": "<exact|partial|semantic|not_matched>",
    "comparisonLanguage": "<ar|en|both>",
    "matchDetails": "<explanation of how match was determined, or why no match>"
  },

  "issuerName": "<issuing authority or organization, or null>",
  "issuerNameAr": "<Arabic issuer name if present, or null>",
  "issuerNameEn": "<English issuer name if present, or null>",

  "issuedDate": "<YYYY-MM-DD|null>",
  "expiryDate": "<YYYY-MM-DD|null>",
  "expirySource": "<explicit|calculated|not_found>",
  "expiryCalculation": {
    "method": "<relative_period|explicit_date|none>",
    "originalText": "<exact text that indicates validity period, or null>",
    "period": "<e.g., '1 year', '6 months', '365 days', or null>",
    "calculatedFrom": "<issuedDate value used for calculation, or null>"
  },

  "validityStatus": "<valid|expired|expiring_soon|unknown>",
  "daysUntilExpiry": null,

  "expiryDetectedFromFooter": false,
  "crossPageLinked": false,
  "isRenewal": false,

  "documentLanguage": "<ar|en|bilingual|unknown>",
  "ocrConfidence": 0.0,

  "confidence": {
    "classification": 0.0,
    "issuer": 0.0,
    "entity": 0.0,
    "dates": 0.0,
    "type": 0.0,
    "bidderMatch": 0.0,
    "typeMatch": 0.0
  },

  "summary": {
    "en": "<concise English summary of document (max 20 words, no dates)>",
    "ar": "<concise Arabic summary of document (max 20 words, no dates)>"
  },

  "extractedFields": {
    "certificateNumber": "<if visible, or null>",
    "registrationNumber": "<if visible, or null>",
    "licenseNumber": "<if visible, or null>",
    "contractNumber": "<if visible, or null>",
    "commercialRegistration": "<if visible, or null>",
    "civilId": "<if visible, or null>",
    "otherIdentifiers": []
  },

  "nonCertificateClassification": {
    "documentType": "<CV|Proposal|Technical_Document|Financial_Document|Letter|Report|Form|Other|null>",
    "documentTypeAr": "<Arabic name or null>",
    "documentTypeEn": "<English name or null>",
    "matchedDocumentTypeId": "<UUID or null>",
    "matchedDocumentTypeName": "<matched type name or null>",
    "typeMatchConfidence": 0.0,
    "typeMatchMethod": "<exact|partial|semantic|no_match|not_applicable>",
    "typeMatchDetails": "<explanation or null>",
    "extractedPersonName": "<for CVs or null>",
    "extractedTitle": "<document title or null>",
    "keyInformation": []
  },

  "reason": "<detailed, human-readable explanation>"
}
```

You MUST include every key. Set values to `null` / `false` / `0.0` as needed.

---

## STEP 1 — Certificate/Contract vs Non-Certificate Classification

Set `"isCertificate": true` **only if at least two** of these cues are present in the text:

### 1.1 Certificate/Contract Terms (English/Arabic)

**English keywords:**
- "Certificate", "License", "Permit", "Registration", "Attestation"
- "Contract", "Agreement", "Memorandum of Understanding", "MOU"
- "Authorization", "Accreditation", "Certification"

**Arabic keywords:**
- "شهادة", "رخصة", "ترخيص", "اعتماد", "إفادة", "إثبات تسجيل"
- "عقد", "اتفاقية", "عقد عمل", "عقد خدمات", "مذكرة تفاهم"
- "تصريح", "إذن", "موافقة"

### 1.2 Official Issuer Indicators

**English:**
- "Ministry", "Authority", "Council", "Chamber", "Municipality"
- "ISO", "Government", "Department", "Bureau", "Commission"

**Arabic:**
- "وزارة", "هيئة", "مجلس", "غرفة تجارة", "بلدية"
- "الهيئة العامة للقوى العاملة", "هيئة أسواق المال"
- "وزارة التجارة والصناعة", "الهيئة العامة للصناعة"

### 1.3 At Least One Recognizable Date (see STEP 5)

### 1.4 Validation/Approval Terms

**English:**
- "issued", "valid", "approved", "certified", "registered", "signed", "executed", "agreed"

**Arabic:**
- "معتمد", "مصادق", "صادر", "ساري", "ساري المفعول", "مجدّد", "موقع", "متفق عليه"

### 1.5 Title-Style Header
Certificate/License/Contract title near the top with an issuer or entity.

### 1.6 Visual/Verification Markers
- "QR", "barcode", "Seal", "Signature", "Stamp"
- "رمز التحقق", "الختم", "توقيع", "ختم"

### 1.7 Contract-Specific Indicators
- Contract number ("رقم العقد"), contract value ("قيمة العقد")
- "الطرف الأول", "الطرف الثاني" (first party, second party)
- Terms and conditions ("الشروط والأحكام")

**If fewer than two cues are present:**
- Set `"isCertificate": false`
- Set extraction fields to `null`
- Keep metadata fields
- Explain in `"reason"`

---

## STEP 2 — STRICT Entity/Bidder Name Extraction and Comparison

### 2.1 Extract Entity Name EXACTLY as Written

**CRITICAL: You MUST extract the entity name exactly as it appears in the certificate.**

Look for entity name in these locations (in order of priority):
1. After "issued to" / "صادرة لـ" / "صادرة إلى"
2. After "company name" / "اسم الشركة"
3. After "entity" / "الجهة" / "المنشأة"
4. In the header/title area of the certificate
5. After "الطرف الثاني" (second party) for contracts
6. After "المقاول" / "المتعهد" / "مقدم الخدمة"

**Extract ALL variations found:**
- `extractedEntityName`: Primary/most complete name
- `extractedEntityNameAr`: Arabic version (if bilingual)
- `extractedEntityNameEn`: English version (if bilingual)

### 2.2 STRICT Bidder Name Comparison

**Compare `extractedEntityName` against `providedBidderName` (from user metadata).**

**Normalization steps before comparison:**
1. Remove extra whitespace
2. Remove punctuation: `.`, `,`, `-`, `'`, `"`
3. Remove legal suffixes: "Co.", "LLC", "W.L.L.", "K.S.C.", "ذ.م.م", "ش.م.ك.", "ش.م.م"
4. Convert to lowercase (for English)
5. Remove "The", "Al-", "ال" prefixes

**Match Types:**

| Match Type | Confidence | Criteria |
|------------|------------|----------|
| `exact` | 0.95-1.0 | Names identical after normalization |
| `partial` | 0.70-0.94 | One name contains the other, or >80% character match |
| `abbreviation` | 0.60-0.85 | Known abbreviation matches (e.g., "KOC" = "Kuwait Oil Company") |
| `mismatch` | 0.0-0.30 | Names clearly different |
| `not_found` | 0.0 | No entity name found in certificate |

**Output structure:**
```json
"bidderNameMatch": {
  "isMatch": true/false,
  "matchType": "exact|partial|abbreviation|mismatch|not_found",
  "matchConfidence": 0.0-1.0,
  "mismatchDetails": "Explanation if mismatch, including what was found vs expected"
}
```

**BE STRICT:** If names don't match, clearly indicate `"isMatch": false` with detailed `mismatchDetails`.

---

## STEP 3 — CERTIFICATE TYPE EXTRACTION AND MATCHING (CRITICAL)

### 3.1 Extract Certificate Type from Document

**Extract the certificate type/title EXACTLY as it appears in the document.**

Look for certificate type in these locations:
1. Document title/header (most reliable)
2. After "Certificate of" / "شهادة"
3. After "License" / "رخصة" / "ترخيص"
4. In bold or emphasized text at the top
5. After "Type:" / "النوع:"

**Extract in both languages if available:**
- `certificateType`: Primary type name found
- `certificateTypeAr`: Arabic version
- `certificateTypeEn`: English version

### 3.2 Match Against Provided Certificate Types List

**You will receive a `certificate_types` array in the metadata containing expected types:**
```json
[
  {"id": "uuid-1", "nameEn": "Commercial Registration", "nameAr": "السجل التجاري"},
  {"id": "uuid-2", "nameEn": "Professional Engineer License", "nameAr": "رخصة مهندس محترف"},
  ...
]
```

**Matching Process:**

1. **Determine comparison language** based on `documentLanguage`:
   - If `documentLanguage` is `"ar"` → Compare `certificateTypeAr` with `nameAr` in list
   - If `documentLanguage` is `"en"` → Compare `certificateTypeEn` with `nameEn` in list
   - If `documentLanguage` is `"bilingual"` → Compare both, prefer exact match

2. **Normalization before comparison:**
   - Remove extra whitespace
   - Remove punctuation
   - Convert to lowercase (for English)
   - Remove common prefixes: "شهادة", "رخصة", "Certificate of", "License"

3. **Match Types:**

| Match Method | Confidence | Criteria |
|--------------|------------|----------|
| `exact` | 0.95-1.0 | Type names identical after normalization |
| `partial` | 0.70-0.94 | One contains the other, or >70% word match |
| `semantic` | 0.50-0.85 | Same meaning but different wording (e.g., "تسجيل تجاري" ≈ "السجل التجاري") |
| `not_matched` | 0.0 | No match found in the list |

4. **Output the match result:**

```json
"certificateTypeMatch": {
  "matchedTypeId": "uuid-of-matched-type or null",
  "matchedTypeNameEn": "English name of matched type or null",
  "matchedTypeNameAr": "Arabic name of matched type or null",
  "isMatched": true/false,
  "matchConfidence": 0.0-1.0,
  "matchMethod": "exact|partial|semantic|not_matched",
  "comparisonLanguage": "ar|en|both",
  "matchDetails": "Explanation of matching logic"
}
```

### 3.3 Matching Examples

**Example 1: Exact Match (Arabic)**
- Extracted: "رخصة مهندس محترف"
- List contains: `{"id": "abc123", "nameAr": "رخصة مهندس محترف", "nameEn": "Professional Engineer License"}`
- Result:
```json
"certificateTypeMatch": {
  "matchedTypeId": "abc123",
  "matchedTypeNameEn": "Professional Engineer License",
  "matchedTypeNameAr": "رخصة مهندس محترف",
  "isMatched": true,
  "matchConfidence": 1.0,
  "matchMethod": "exact",
  "comparisonLanguage": "ar",
  "matchDetails": "Exact match found for Arabic certificate type"
}
```

**Example 2: Partial Match (English)**
- Extracted: "Commercial Registration Certificate"
- List contains: `{"id": "def456", "nameAr": "السجل التجاري", "nameEn": "Commercial Registration"}`
- Result:
```json
"certificateTypeMatch": {
  "matchedTypeId": "def456",
  "matchedTypeNameEn": "Commercial Registration",
  "matchedTypeNameAr": "السجل التجاري",
  "isMatched": true,
  "matchConfidence": 0.85,
  "matchMethod": "partial",
  "comparisonLanguage": "en",
  "matchDetails": "Partial match: extracted 'Commercial Registration Certificate' contains 'Commercial Registration'"
}
```

**Example 3: No Match**
- Extracted: "ISO 9001 Quality Certificate"
- List does not contain any ISO-related type
- Result:
```json
"certificateTypeMatch": {
  "matchedTypeId": null,
  "matchedTypeNameEn": null,
  "matchedTypeNameAr": null,
  "isMatched": false,
  "matchConfidence": 0.0,
  "matchMethod": "not_matched",
  "comparisonLanguage": "en",
  "matchDetails": "No matching certificate type found in provided list for 'ISO 9001 Quality Certificate'"
}
```

---

## STEP 4 — OCR Confidence Adjustment

Base `ocrConfidence` on provided metadata. Adjust other confidences:

| OCR Confidence | Adjustment |
|----------------|------------|
| ≥ 0.90 | Keep as-is |
| 0.75–0.89 | Reduce confidences by ~0.1 |
| < 0.75 | Reduce confidences by ~0.2, mention in `"reason"` |

---

## STEP 5 — Date Detection (STRICT Expiry Calculation)

### 5.1 Recognize Date Formats

**Western formats:**
- `DD/MM/YYYY`, `DD-MM-YYYY`, `YYYY-MM-DD`, `YYYY/MM/DD`
- `DD Month YYYY` (e.g., "19 August 2019")
- `Month DD, YYYY` (e.g., "August 19, 2019")

**Arabic formats:**
- Arabic digits: `٢٠٢٥/٠٧/١٥` → normalize to `2025/07/15`
- Hijri dates: Note if Hijri, attempt conversion or flag as uncertain

**Always normalize Arabic digits (٠١٢٣٤٥٦٧٨٩) to English digits.**

### 5.2 Context Labels for Dates

Search **±15 words (~120 characters)** around each date.

**Issue Date Keywords:**
- English: "issue", "issued on", "date of issue", "valid from", "start date", "effective from", "signing date"
- Arabic: "تاريخ الإصدار", "تاريخ السريان", "صادر بتاريخ", "بدء السريان", "تاريخ التوقيع", "تاريخ العقد"

**Expiry Date Keywords:**
- English: "expiry", "expires on", "valid until", "expiration", "expiry date", "valid through", "end date"
- Arabic: "تاريخ الانتهاء", "تاريخ انتهاء", "تاريخ الصلاحية", "صالح حتى", "حتى تاريخ", "نهاية الصلاحية", "ينتهي في"

### 5.3 STRICT Relative Validity Calculation (CRITICAL)

**CRITICAL: If certificate states validity as a PERIOD, you MUST calculate the expiry date.**

**Relative Validity Patterns to Detect:**

| Pattern (English) | Pattern (Arabic) | Action |
|-------------------|------------------|--------|
| "valid for X year(s)" | "صالح لمدة X سنة/سنوات" | Calculate: issuedDate + X years |
| "valid for X month(s)" | "صالح لمدة X شهر/أشهر" | Calculate: issuedDate + X months |
| "valid for X day(s)" | "صالح لمدة X يوم/أيام" | Calculate: issuedDate + X days |
| "expires after X year(s)" | "ينتهي بعد X سنة" | Calculate: issuedDate + X years |
| "validity period: X" | "مدة الصلاحية: X" | Calculate accordingly |
| "renewable annually" | "يجدد سنوياً" | Calculate: issuedDate + 1 year |
| "one year validity" | "صلاحية سنة واحدة" | Calculate: issuedDate + 1 year |
| "two year validity" | "صلاحية سنتين" | Calculate: issuedDate + 2 years |

**Number Recognition (Arabic words):**
- واحد/واحدة = 1
- اثنان/اثنين/سنتين = 2
- ثلاث/ثلاثة = 3
- أربع/أربعة = 4
- خمس/خمسة = 5
- ست/ستة = 6
- سبع/سبعة = 7
- ثمان/ثمانية = 8
- تسع/تسعة = 9
- عشر/عشرة = 10

**Calculation Process:**

1. **Find issue date** (explicit or inferred)
2. **Detect relative validity phrase**
3. **Extract period value and unit**
4. **Calculate expiry date:**
   - For years: Add X years to issue date
   - For months: Add X months to issue date
   - For days: Add X days to issue date

**Output the calculation details:**
```json
"expirySource": "calculated",
"expiryCalculation": {
  "method": "relative_period",
  "originalText": "صالح لمدة سنة واحدة من تاريخ الإصدار",
  "period": "1 year",
  "calculatedFrom": "2024-03-15"
}
```

**If issue date is missing but relative validity is mentioned:**
- Set `"expiryDate": null`
- Set `"expirySource": "not_found"`
- Document in `"reason"`: "Relative validity mentioned (X period) but issue date missing — cannot calculate expiry."

### 5.4 Expiry Date Priority

1. **Explicit expiry date** (highest priority)
2. **Calculated from relative validity** (second priority)
3. **Inferred from context** (lowest priority)

### 5.5 Date Validation Rules

- If `expiryDate < issuedDate`: Discard both, set to `null`, explain in reason
- If expiry date is in the past: Set `"validityStatus": "expired"`
- If expiry date is within 30 days: Set `"validityStatus": "expiring_soon"`

---

## STEP 6 — Cross-Page and Renewal Handling

### 6.1 Cross-Page Linking
If dates are split across pages of the same certificate:
- Set `"crossPageLinked": true`
- Explain in `"reason"`

### 6.2 Renewal Detection
If renewal phrases appear ("تجديد", "renewal", "reissued"):
- Set `"isRenewal": true`
- Use the LATEST validity period
- Explain in `"reason"`

---

## STEP 7 — Summary

Provide a concise bilingual summary (max 20 words per language):
- What type of document this is
- Who issued it
- Who it's issued to
- Its purpose/relevance to tender

**DO NOT include any dates in the summary.**

**Examples:**

For a certificate:
```json
"summary": {
  "en": "Commercial registration certificate issued by Ministry of Commerce for ABC Company.",
  "ar": "شهادة سجل تجاري صادرة من وزارة التجارة لشركة ABC."
}
```

For a non-certificate:
```json
"summary": {
  "en": "Supporting document attached to tender submission, not an official certificate.",
  "ar": "مستند داعم مرفق بعرض المناقصة، ليس شهادة رسمية."
}
```

---

## STEP 8 — Extract Additional Identifiers

Extract any visible identification numbers:

```json
"extractedFields": {
  "certificateNumber": "CERT-2024-12345",
  "registrationNumber": "REG-98765",
  "licenseNumber": null,
  "contractNumber": null,
  "commercialRegistration": "12345",
  "civilId": null,
  "otherIdentifiers": ["QR Code: ABC123", "File No: F-2024-001"]
}
```

---

## STEP 9 — Detailed Reason Field

The `"reason"` field MUST include:

1. **Classification justification:**
   - Why it IS or IS NOT a certificate
   - Which cues were detected

2. **Entity/Bidder name analysis:**
   - What entity name was extracted
   - How it compares to provided bidder name
   - Match confidence explanation

3. **Certificate type matching:**
   - What certificate type was extracted
   - Whether it matched any type in the provided list
   - Match method and confidence

4. **Date analysis:**
   - What dates were found
   - How expiry was determined (explicit vs calculated)
   - If calculated, show the calculation

5. **Validity assessment:**
   - Current validity status
   - Any concerns or uncertainties

**Example reason:**
```
"Certificate detected: Commercial Registration from Ministry of Commerce.
Entity name extracted: 'شركة الخليج للتجارة' matches provided bidder 'Gulf Trading Company' (partial match, Arabic-English translation, confidence: 0.85).
Certificate type: 'السجل التجاري' matched to 'Commercial Registration' (ID: abc-123) with exact match (confidence: 1.0).
Issue date: 2024-01-15 found explicitly.
Expiry: Calculated from 'صالح لمدة سنة واحدة' (valid for one year) → 2025-01-15.
Status: Valid (expires in 245 days)."
```

---

## STEP 10 — Final Consistency Checks

Before returning JSON:

1. **Date consistency:** If `expiryDate < issuedDate`, set both to `null`

2. **Required fields for certificates:**
   - If `isCertificate: true` but `issuerName` or `certificateType` is null → lower `confidence.classification` to ≤ 0.7

3. **Bidder match consistency:**
   - If `extractedEntityName` is null → `bidderNameMatch.matchType` must be `"not_found"`
   - If names don't match → `bidderNameMatch.isMatch` must be `false`

4. **Certificate type match consistency:**
   - If `certificateType` is null → `certificateTypeMatch.matchMethod` must be `"not_matched"`
   - If no match found → `certificateTypeMatch.matchedTypeId` must be `null`

5. **Summary and reason:** Must always be present and non-empty

6. **Expiry calculation:** If relative validity detected, `expiryCalculation` must be populated

---

## STEP 11 — Output Rules

1. Output **only one JSON object** — no markdown, no extra text
2. Include **ALL keys** as defined in OUTPUT FORMAT
3. Extract **only explicitly visible information** — no guessing
4. **Be STRICT** with bidder name matching — flag any discrepancies
5. **Be STRICT** with certificate type matching — use correct language for comparison
6. **Always calculate expiry** from relative validity periods when possible
7. Use `null` for missing values, not empty strings
8. Confidence scores must be between 0.0 and 1.0
9. Dates must be in `YYYY-MM-DD` format

## STEP 12 — NON-CERTIFICATE DOCUMENT TYPE DETECTION (NEW)

**When `isCertificate` is `false`, you MUST still analyze and classify the document type.**

### 12.1 Non-Certificate Document Types to Detect

| Document Type | Arabic | Keywords/Indicators |
|---------------|--------|---------------------|
| `CV` | سيرة ذاتية | "CV", "Resume", "Curriculum Vitae", "سيرة ذاتية", personal info, education, experience sections |
| `Proposal` | عرض فني/مالي | "Proposal", "عرض", "Technical Proposal", "Financial Proposal", "عرض فني", "عرض مالي" |
| `Technical_Document` | وثيقة فنية | "Technical Specification", "المواصفات الفنية", drawings, diagrams |
| `Financial_Document` | وثيقة مالية | "Financial Statement", "القوائم المالية", "Balance Sheet", "ميزانية" |
| `Letter` | خطاب | "Letter", "خطاب", "To Whom It May Concern", "إلى من يهمه الأمر" |
| `Report` | تقرير | "Report", "تقرير", analysis, findings |
| `Form` | نموذج | "Form", "نموذج", "Application", "طلب" |
| `Other` | أخرى | Does not match any above category |

### 12.2 Non-Certificate Output Fields (NEW)

**Add these fields to your JSON output for ALL documents (certificate or not):**
```json
"nonCertificateClassification": {
  "documentType": "<CV|Proposal|Technical_Document|Financial_Document|Letter|Report|Form|Other>",
  "documentTypeAr": "<Arabic name of document type>",
  "documentTypeEn": "<English name of document type>",
  "matchedDocumentTypeId": "<UUID from certificate_types list if matches, or null>",
  "matchedDocumentTypeName": "<Name of matched type from list, or null>",
  "typeMatchConfidence": 0.0,
  "typeMatchMethod": "<exact|partial|semantic|no_match>",
  "typeMatchDetails": "<explanation of how document type was determined and matched>",
  "extractedPersonName": "<for CVs: person's name, or null>",
  "extractedTitle": "<document title if visible, or null>",
  "keyInformation": ["<list of key extracted info>"]
}
```

### 12.3 Match Non-Certificate Against certificate_types List

**IMPORTANT:** The `certificate_types` list may also contain non-certificate document types like "CV" or "سيرة ذاتية".

**Matching Process for Non-Certificates:**

1. Detect the document type (CV, Proposal, etc.)
2. Search the `certificate_types` list for matching entries:
   - Compare detected type against `nameEn` and `nameAr`
   - Use flexible matching (exact, partial, semantic)
3. If match found:
   - Set `matchedDocumentTypeId` to the matched type's `id`
   - Set `typeMatchConfidence` based on match quality
4. If no match:
   - Set `matchedDocumentTypeId` to `null`
   - Set `typeMatchMethod` to `"no_match"`

### 12.4 CV Detection (Special Case)

**For CVs/Resumes, extract additional information:**

CV Indicators:
- "CV", "Resume", "Curriculum Vitae", "سيرة ذاتية"
- Personal information section (name, contact, nationality)
- Education section ("Education", "التعليم", "المؤهلات")
- Experience section ("Experience", "الخبرات", "Work History")
- Skills section ("Skills", "المهارات")

**Extract from CV:**
- `extractedPersonName`: The person's full name
- `keyInformation`: Key skills, qualifications, years of experience

### 12.5 Examples

**Example 1: CV Document**
```json
"isCertificate": false,
"nonCertificateClassification": {
  "documentType": "CV",
  "documentTypeAr": "سيرة ذاتية",
  "documentTypeEn": "CV",
  "matchedDocumentTypeId": "uuid-of-cv-type-if-in-list",
  "matchedDocumentTypeName": "CV / سيرة ذاتية",
  "typeMatchConfidence": 0.95,
  "typeMatchMethod": "exact",
  "typeMatchDetails": "Document identified as CV based on presence of personal info, education, and experience sections. Matched to 'CV' type in certificate_types list.",
  "extractedPersonName": "براء خلف",
  "extractedTitle": "Software Engineer CV",
  "keyInformation": ["5 years experience", "Python, JavaScript", "BSc Computer Science"]
},
"reason": "This document is classified as non-certificate. It is a CV/Resume for براء خلف, containing personal information, education history, and work experience. Document type 'CV' matched to certificate_types list with ID: uuid-xxx (confidence: 0.95). No certificate indicators present - no official issuer, no certificate title, no validity dates."
```

**Example 2: Proposal Document**
```json
"isCertificate": false,
"nonCertificateClassification": {
  "documentType": "Proposal",
  "documentTypeAr": "عرض فني",
  "documentTypeEn": "Technical Proposal",
  "matchedDocumentTypeId": null,
  "matchedDocumentTypeName": null,
  "typeMatchConfidence": 0.0,
  "typeMatchMethod": "no_match",
  "typeMatchDetails": "Document identified as Technical Proposal but no matching type found in certificate_types list.",
  "extractedPersonName": null,
  "extractedTitle": "Technical Proposal for IT Infrastructure",
  "keyInformation": ["Project scope", "Timeline: 6 months", "Team: 5 engineers"]
},
"reason": "This document is classified as non-certificate. It is a Technical Proposal document containing project scope and methodology. No matching document type found in provided certificate_types list. No certificate indicators present."
```

---

## UPDATED OUTPUT FORMAT

**Add the `nonCertificateClassification` object to your JSON output:**
```json
{
  "isCertificate": true/false,

  // ... ALL EXISTING FIELDS UNCHANGED ...

  // NEW FIELD - Always include this
  "nonCertificateClassification": {
    "documentType": "<CV|Proposal|Technical_Document|Financial_Document|Letter|Report|Form|Other|null>",
    "documentTypeAr": "<Arabic name or null>",
    "documentTypeEn": "<English name or null>",
    "matchedDocumentTypeId": "<UUID or null>",
    "matchedDocumentTypeName": "<matched type name or null>",
    "typeMatchConfidence": 0.0,
    "typeMatchMethod": "<exact|partial|semantic|no_match|not_applicable>",
    "typeMatchDetails": "<explanation or null>",
    "extractedPersonName": "<for CVs or null>",
    "extractedTitle": "<document title or null>",
    "keyInformation": []
  },

  "reason": "<updated to include non-certificate classification details>"
}
```

**Rules:**
- If `isCertificate: true` → Set `nonCertificateClassification.documentType` to `null` and `typeMatchMethod` to `"not_applicable"`
- If `isCertificate: false` → MUST populate `nonCertificateClassification` with detected type
- Always try to match against `certificate_types` list even for non-certificates
"""

    def __init__(self):
        """Initialize the Vertex AI client with gemini-2.5-pro model."""
        vertexai.init(
            project=settings.gcp_project_id,
            location=settings.vertex_ai_location
        )
        # Use gemini-2.5-pro as specified in n8n workflow
        self.model = GenerativeModel("gemini-2.5-pro")
        logger.info("Initialized CertificateExtractionService with gemini-2.5-pro model")

    def _build_user_prompt(
        self,
        ocr_text: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Build the user prompt from n8n template with variable substitution.

        Args:
            ocr_text: The OCR extracted text from the document
            metadata: Dictionary containing all metadata fields

        Returns:
            Complete user prompt with all variables substituted
        """
        # Extract metadata fields with defaults
        page_number = metadata.get('page_number', 1)
        total_pages = metadata.get('total_pages', 1)
        rfp_number = metadata.get('rfp_number', 'N/A')
        cert_request_id = metadata.get('cert_request_id', 'N/A')
        file_id = metadata.get('file_Id', metadata.get('file_id', 'N/A'))
        bidder_name = metadata.get('bidder_name', 'N/A')
        language = metadata.get('language', 'unknown')
        confidence = metadata.get('confidence', 'N/A')
        certificate_types = metadata.get('certificate_types', [])

        # Format certificate_types as JSON string
        cert_types_json = json.dumps(certificate_types, ensure_ascii=False, indent=2)

        # Format full metadata as JSON string
        metadata_json = json.dumps(metadata, ensure_ascii=False, indent=2)

        # Build the user prompt exactly as in n8n template
        user_prompt = f"""You are analyzing page {page_number} of {total_pages} from a bidder's tender submission.

=== REQUEST INFORMATION ===
RFP Number: {rfp_number}
Request ID: {cert_request_id}
File ID: {file_id}

=== BIDDER INFORMATION (User Provided - Compare Against Certificate) ===
Provided Bidder Name: {bidder_name}

=== EXPECTED CERTIFICATE/DOCUMENT TYPES (Match extracted type against this list) ===
{cert_types_json}

=== DOCUMENT INFORMATION ===
Det ected Language: {language}
Page: {page_number} of {total_pages}
OCR Confidence: {confidence}

=== OCR EXTRACTED TEXT ===
\"\"\"
{ocr_text}
\"\"\"

=== FULL METADATA ===
{metadata_json}

=== YOUR TASK ===

1. **CLASSIFY**: Determine if this page is an official certificate, license, or contract.

2. **IF CERTIFICATE (isCertificate: true):**
   - Extract entity name EXACTLY as written
   - Compare against "{bidder_name}" (be STRICT)
   - Match certificate type against certificate_types list
   - Extract dates (explicit or calculated)
   - Set nonCertificateClassification.documentType to null

3. **IF NOT CERTIFICATE (isCertificate: false):**
   - **DETECT DOCUMENT TYPE**: Identify what type of document this is:
     * CV/Resume (سيرة ذاتية)
     * Proposal (عرض)
     * Technical Document (وثيقة فنية)
     * Financial Document (وثيقة مالية)
     * Letter (خطاب)
     * Report (تقرير)
     * Form (نموذج)
     * Other (أخرى)
   - **MATCH AGAINST LIST**: Check if this document type exists in the certificate_types list above
   - **EXTRACT KEY INFO**: For CVs, extract person name and key qualifications
   - Populate the nonCertificateClassification object completely

4. **CERTIFICATE TYPE MATCHING** (For certificates):
   - Use CORRECT LANGUAGE for comparison (Arabic→nameAr, English→nameEn)
   - Return matched type's ID if found

5. **NON-CERTIFICATE TYPE MATCHING** (For non-certificates):
   - Match detected document type against certificate_types list
   - Example: If document is a CV and list contains {{"nameEn": "CV", "nameAr": "سيرة ذاتية", "id": "xxx"}}
   - Set matchedDocumentTypeId to "xxx"

6. **PROVIDE SUMMARY**:
   - Short bilingual summary (no dates)
   - Include document type classification in reason

Return ONLY a valid JSON object following the schema provided in your instructions.
**IMPORTANT**: Always include the nonCertificateClassification object in your response.
"""

        return user_prompt

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response from AI, handling markdown code blocks.

        Args:
            response_text: Raw response text from the AI model

        Returns:
            Parsed JSON dictionary

        Raises:
            json.JSONDecodeError: If JSON parsing fails
        """
        # Remove markdown code blocks if present
        text = response_text.strip()

        # Remove ```json prefix
        if text.startswith("```json"):
            text = text[7:]
        # Remove ``` prefix
        elif text.startswith("```"):
            text = text[3:]

        # Remove ``` suffix
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        # Parse JSON
        return json.loads(text)

    async def extract_certificate_data(
        self,
        ocr_text: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract structured certificate data from OCR text using AI.

        This method replicates the n8n "LLM – Certificate Extraction Agent" node
        by using the exact same system prompt, user prompt template, and model.

        Args:
            ocr_text: Normalized OCR text from the certificate
            metadata: Dictionary containing:
                - page_number: Current page number
                - total_pages: Total number of pages
                - rfp_number: RFP/tender number
                - cert_request_id: Certificate request ID
                - file_Id: File ID
                - bidder_name: Bidder name to compare against
                - language: Detected language
                - confidence: OCR confidence score
                - certificate_types: List of expected certificate types with id, nameEn, nameAr

        Returns:
            Dictionary with extracted certificate data matching n8n output structure
        """
        try:
            # Build the user prompt from n8n template
            user_prompt = self._build_user_prompt(
                ocr_text=ocr_text,
                metadata=metadata
            )

            # Configure generation parameters (matching n8n settings)
            generation_config = GenerationConfig(
                temperature=0.1,  # Low temperature for consistent extraction
                top_p=0.95,
                top_k=40,
                max_output_tokens=4096,  # Increased for full output structure
                response_mime_type="application/json"
            )

            # Call the AI model with system prompt and user prompt
            logger.info(
                f"Calling Gemini 2.5 Pro for certificate extraction "
                f"(page {metadata.get('page_number', 1)})"
            )

            response = self.model.generate_content(
                [self.SYSTEM_PROMPT, user_prompt],
                generation_config=generation_config
            )

            # Parse the JSON response
            result_text = response.text.strip()
            logger.debug(f"Raw AI response: {result_text[:500]}...")

            extraction_result = self._parse_json_response(result_text)

            # Ensure metadata fields are preserved in the output
            extraction_result['cert_request_id'] = metadata.get('cert_request_id')
            extraction_result['fileId'] = metadata.get('file_Id', metadata.get('file_id'))
            extraction_result['rfpNumber'] = metadata.get('rfp_number')
            extraction_result['pageNumber'] = metadata.get('page_number', 1)
            extraction_result['totalPages'] = metadata.get('total_pages', 1)
            extraction_result['providedBidderName'] = metadata.get('bidder_name')
            extraction_result['ocrConfidence'] = metadata.get('confidence', 0.0)

            logger.info(
                f"Certificate extraction completed for page {metadata.get('page_number', 1)}: "
                f"isCertificate={extraction_result.get('isCertificate', False)}"
            )

            return extraction_result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            logger.debug(f"Raw response: {result_text}")

            # Return error structure matching n8n format
            return {
                "isCertificate": False,
                "cert_request_id": metadata.get('cert_request_id'),
                "fileId": metadata.get('file_Id', metadata.get('file_id')),
                "rfpNumber": metadata.get('rfp_number'),
                "pageNumber": metadata.get('page_number', 1),
                "totalPages": metadata.get('total_pages', 1),
                "extractedEntityName": None,
                "providedBidderName": metadata.get('bidder_name'),
                "bidderNameMatch": {
                    "isMatch": False,
                    "matchType": "not_found",
                    "matchConfidence": 0.0,
                    "mismatchDetails": "JSON parsing error"
                },
                "certificateType": None,
                "certificateTypeMatch": {
                    "matchedTypeId": None,
                    "matchedTypeNameEn": None,
                    "matchedTypeNameAr": None,
                    "isMatched": False,
                    "matchConfidence": 0.0,
                    "matchMethod": "not_matched",
                    "comparisonLanguage": "en",
                    "matchDetails": "Extraction failed due to JSON parsing error"
                },
                "nonCertificateClassification": {
                    "documentType": "Other",
                    "documentTypeAr": "خطأ في المعالجة",
                    "documentTypeEn": "Processing Error",
                    "matchedDocumentTypeId": None,
                    "matchedDocumentTypeName": None,
                    "typeMatchConfidence": 0.0,
                    "typeMatchMethod": "no_match",
                    "typeMatchDetails": f"JSON parsing error: {str(e)}",
                    "extractedPersonName": None,
                    "extractedTitle": None,
                    "keyInformation": []
                },
                "reason": f"Failed to parse AI response as JSON: {str(e)}",
                "error": f"JSON parsing error: {str(e)}"
            }

        except Exception as e:
            logger.error(f"Certificate extraction failed: {e}")

            # Return error structure matching n8n format
            return {
                "isCertificate": False,
                "cert_request_id": metadata.get('cert_request_id'),
                "fileId": metadata.get('file_Id', metadata.get('file_id')),
                "rfpNumber": metadata.get('rfp_number'),
                "pageNumber": metadata.get('page_number', 1),
                "totalPages": metadata.get('total_pages', 1),
                "extractedEntityName": None,
                "providedBidderName": metadata.get('bidder_name'),
                "bidderNameMatch": {
                    "isMatch": False,
                    "matchType": "not_found",
                    "matchConfidence": 0.0,
                    "mismatchDetails": "Extraction error"
                },
                "certificateType": None,
                "certificateTypeMatch": {
                    "matchedTypeId": None,
                    "matchedTypeNameEn": None,
                    "matchedTypeNameAr": None,
                    "isMatched": False,
                    "matchConfidence": 0.0,
                    "matchMethod": "not_matched",
                    "comparisonLanguage": "en",
                    "matchDetails": f"Extraction failed: {str(e)}"
                },
                "nonCertificateClassification": {
                    "documentType": "Other",
                    "documentTypeAr": "خطأ في المعالجة",
                    "documentTypeEn": "Processing Error",
                    "matchedDocumentTypeId": None,
                    "matchedDocumentTypeName": None,
                    "typeMatchConfidence": 0.0,
                    "typeMatchMethod": "no_match",
                    "typeMatchDetails": f"Extraction error: {str(e)}",
                    "extractedPersonName": None,
                    "extractedTitle": None,
                    "keyInformation": []
                },
                "reason": f"Certificate extraction failed: {str(e)}",
                "error": str(e)
            }

    async def extract_from_pages(
        self,
        pages: List[Dict[str, Any]],
        bidder_name: str,
        certificate_types: List[Dict[str, Any]],
        rfp_number: str,
        cert_request_id: str = None,
        file_id: str = None
    ) -> List[Dict[str, Any]]:
        """Extract certificate data from multiple pages.

        Args:
            pages: List of page dictionaries with 'text' field
            bidder_name: Official bidder name
            certificate_types: List of certificate types with id, nameEn, nameAr
            rfp_number: RFP number
            cert_request_id: Optional certificate request ID
            file_id: Optional file ID

        Returns:
            List of extraction results, one per page
        """
        results = []

        for page in pages:
            page_number = page.get('page_number', 1)
            text = page.get('text', '')

            if not text.strip():
                logger.warning(f"Page {page_number} has no text, skipping extraction")
                results.append({
                    "isCertificate": False,
                    "pageNumber": page_number,
                    "totalPages": len(pages),
                    "cert_request_id": cert_request_id,
                    "fileId": file_id,
                    "rfpNumber": rfp_number,
                    "reason": "Empty page - no text to analyze",
                    "nonCertificateClassification": {
                        "documentType": "Other",
                        "documentTypeAr": "صفحة فارغة",
                        "documentTypeEn": "Empty Page",
                        "matchedDocumentTypeId": None,
                        "matchedDocumentTypeName": None,
                        "typeMatchConfidence": 0.0,
                        "typeMatchMethod": "no_match",
                        "typeMatchDetails": "Page contains no text",
                        "extractedPersonName": None,
                        "extractedTitle": None,
                        "keyInformation": []
                    }
                })
                continue

            # Normalize the text first
            normalized_text = TextNormalizer.normalize_full_text(text)

            # Build metadata dictionary for this page
            metadata = {
                'page_number': page_number,
                'total_pages': len(pages),
                'rfp_number': rfp_number,
                'cert_request_id': cert_request_id or 'N/A',
                'file_Id': file_id or 'N/A',
                'bidder_name': bidder_name,
                'language': page.get('language', 'unknown'),
                'confidence': page.get('confidence', 0.0),
                'certificate_types': certificate_types
            }

            # Extract data
            extraction = await self.extract_certificate_data(
                ocr_text=normalized_text,
                metadata=metadata
            )

            # Add original and normalized text for reference
            extraction['original_text'] = text
            extraction['normalized_text'] = normalized_text

            results.append(extraction)

        logger.info(
            f"Completed extraction for {len(results)} pages, "
            f"{sum(1 for r in results if r.get('isCertificate'))} certificates found"
        )

        return results
