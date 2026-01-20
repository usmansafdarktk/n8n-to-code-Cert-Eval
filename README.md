# Certificate Validation Agent

AI-powered certificate validation system with OCR, document analysis, and automated compliance checking.

## Features

- 📄 **PDF Processing**: OCR extraction from certificate PDFs
- 🤖 **AI Analysis**: Google Vertex AI (Gemini 2.5) for intelligent certificate parsing
- ✅ **Validation**: Automated compliance checking against business rules
- 🔍 **Vector Search**: PGVector embeddings for semantic document search
- 🌐 **Multi-language**: Arabic and English support with automatic detection
- 📊 **Reporting**: Comprehensive validation reports with missing certificates tracking
- 🔐 **Secure**: JWT authentication and Google Cloud Storage integration

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL 15+ with PGVector extension
- **AI/ML**: Google Vertex AI (Gemini, Embeddings)
- **Storage**: Google Cloud Storage
- **OCR**: External OCR API integration
- **ORM**: SQLAlchemy 2.0 (async)

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 15+ with PGVector extension
- Google Cloud Platform account with:
  - Cloud Storage bucket
  - Vertex AI API enabled
  - Service account key
- Redis (optional, for caching)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd certificate-validation-app
```

### 2. Install dependencies

Using Poetry (recommended):
```bash
poetry install
```

Or using pip:
```bash
pip install -r requirements.txt
```

### 3. Configure environment

Copy `.env.example` to `.env` and update values:

```bash
cp .env.example .env
```

Key settings:
- `DATABASE_URL`: PostgreSQL connection string
- `GCP_PROJECT_ID`: Your GCP project ID
- `GCS_BUCKET_NAME`: Cloud Storage bucket name
- `GCP_SERVICE_ACCOUNT_KEY_PATH`: Path to service account JSON key
- `JWT_SECRET_KEY`: Secret key for JWT tokens
- `OCR_API_URL`: OCR service endpoint

### 4. Setup database

Run migrations:
```bash
poetry run alembic upgrade head
```

Or manually create tables:
```bash
poetry run python -m app.scripts.init_db
```

### 5. Run the application

Development mode:
```bash
poetry run uvicorn app.main:app --reload --port 8000
```

Production mode:
```bash
poetry run python app/main.py
```

## Docker Setup

### Using Docker Compose

```bash
docker-compose up -d
```

This will start:
- FastAPI application (port 8000)
- PostgreSQL with PGVector (port 5432)
- Redis (port 6379)

### Build Docker image

```bash
docker build -t certificate-validation-agent .
```

## API Endpoints

### Authentication
- All endpoints require JWT token in Authorization header: `Bearer <token>`

### Core Endpoints

#### Start Certificate Validation
```http
POST /api/start-processing
Content-Type: application/json
Authorization: Bearer <token>

{
  "rfp_number": "RFP2024-001",
  "bidder_name": "ABC Company",
  "warning_start_date": "2025-01-10",
  "warning_end_date": "2025-02-10",
  "certificate_types": [
    {"id": "uuid", "nameEn": "ISO 9001", "nameAr": "آيزو 9001"}
  ],
  "files": [
    {"id": "uuid", "fileName": "cert.pdf", "signed_url": "https://..."}
  ]
}
```

#### Upload File
```http
POST /api/files/upload
Content-Type: multipart/form-data

file: <binary>
```

#### Get Signed URL
```http
GET /api/files/{file_id}/signed-url
```

#### Get Requests Summary
```http
GET /api/requests/summary
```

#### Get Request Details
```http
GET /api/requests/{request_id}/details
```

#### Get Missing Certificates
```http
GET /api/requests/{request_id}/missing-certificates
```

#### Get Other Documents (non-certificates)
```http
GET /api/requests/{request_id}/other-documents
```

### Certificate Types Management

#### List Certificate Types
```http
GET /api/certificate-types
```

#### Create Certificate Type
```http
POST /api/certificate-types
{
  "name_en": "ISO 9001",
  "name_ar": "آيزو 9001",
  "issuer": "ISO Organization",
  "created_by": "admin"
}
```

#### Update Certificate Type
```http
PUT /api/certificate-types/{id}
{
  "name_en": "ISO 9001:2015",
  "updated_by": "admin"
}
```

#### Delete Certificate Type (soft delete)
```http
DELETE /api/certificate-types/{id}?updated_by=admin
```

## Architecture

```
┌─────────────────┐
│   FastAPI App   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼───────┐
│  API  │ │ Services │
│ Layer │ │  Layer   │
└───┬───┘ └──┬───────┘
    │        │
    │   ┌────┴──────────────┐
    │   │                   │
┌───▼───▼──┐  ┌────────────▼─────┐
│PostgreSQL│  │ Google Cloud     │
│+PGVector │  │ (Storage + AI)   │
└──────────┘  └──────────────────┘
```

### Key Services

1. **FileStorageService**: Upload/download files, generate signed URLs
2. **OCRService**: Extract text from PDFs using external OCR API
3. **CertificateExtractionService**: AI-powered parsing with Gemini
4. **ValidationService**: Business rules validation
5. **VectorEmbeddingService**: Generate and store embeddings

## Validation Rules

The system validates certificates against:

1. **Expiry Date Required**: Certificate must have expiry date
2. **Not Expired**: Current date must be before expiry
3. **Warning Period**: Alert if expiring within warning window
4. **Date Order**: Issue date must be before expiry date
5. **Bidder Name Match**: Certificate entity must match provided bidder
6. **Certificate Type**: Must match expected types list
7. **Missing Certificates**: Identify required certificates not submitted

## Development

### Run tests
```bash
poetry run pytest
```

### Code formatting
```bash
poetry run black app/
poetry run ruff check app/
```

### Type checking
```bash
poetry run mypy app/
```

## Production Deployment

### Environment Variables

Ensure all production values are set:
- Strong `JWT_SECRET_KEY`
- Production database credentials
- GCP service account with minimal permissions
- `DEBUG=false`
- Configure proper CORS origins

### Security Checklist

- [ ] Use HTTPS only
- [ ] Rotate JWT secrets regularly
- [ ] Limit file upload sizes
- [ ] Enable rate limiting
- [ ] Configure firewall rules
- [ ] Use read-only database user for queries
- [ ] Store secrets in secret manager (not .env)
- [ ] Enable audit logging

## License

MIT License

## Support

For issues and questions, please open a GitHub issue.
