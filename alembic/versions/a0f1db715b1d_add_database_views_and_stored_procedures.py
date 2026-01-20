"""Add database views and stored procedures

Revision ID: a0f1db715b1d
Revises: ccfd06a73a85
Create Date: 2026-01-19 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0f1db715b1d'
down_revision: Union[str, None] = 'ccfd06a73a85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """Create database views and stored procedures."""

    # Create requests summary view
    op.execute("""
        CREATE OR REPLACE VIEW vw_requests_summary AS
        SELECT
            r.id,
            r.rfpnumber,
            r.biddername,
            r.statuscode,
            r.created_date,
            r.completeddate,
            r.user_email,
            COUNT(DISTINCT c.id) as total_certificates,
            COUNT(DISTINCT CASE WHEN c.validation_status = 'PASSED' THEN c.id END) as passed_certificates,
            COUNT(DISTINCT CASE WHEN c.validation_status = 'FAILED' THEN c.id END) as failed_certificates,
            COUNT(DISTINCT CASE WHEN c.validation_status = 'WARNING' THEN c.id END) as warning_certificates,
            COUNT(DISTINCT mc.id) as missing_certificates_count
        FROM request r
        LEFT JOIN certificate c ON r.id = c.requestid
        LEFT JOIN missingcertificate mc ON r.id = mc.requestid
        GROUP BY r.id, r.rfpnumber, r.biddername, r.statuscode,
                 r.created_date, r.completeddate, r.user_email
    """)

    # Create requests detailed view
    op.execute("""
        CREATE OR REPLACE VIEW vw_requests_detailed AS
        SELECT
            r.id,
            r.rfpnumber,
            r.biddername,
            r.statuscode,
            r.summary,
            r.warningstartdate,
            r.warningenddate,
            r.created_date,
            r.completeddate,
            r.user_email,
            r.created_by,
            COALESCE(
                json_agg(
                    DISTINCT jsonb_build_object(
                        'id', c.id,
                        'certificate_name', c.certificatename,
                        'extracted_bidder_name', c.extractedbiddername,
                        'issuer_name', c.issuername,
                        'issue_date', c.issuedate,
                        'expiry_date', c.expirydate,
                        'validation_status', c.validation_status,
                        'validation_issues', c.validation_issues,
                        'validation_warnings', c.validation_warnings
                    )
                ) FILTER (WHERE c.id IS NOT NULL),
                '[]'::json
            ) as certificates,
            COALESCE(
                json_agg(
                    DISTINCT jsonb_build_object(
                        'id', mc.id,
                        'certificate_type_id', mc.certificatetypeid,
                        'status', mc.status
                    )
                ) FILTER (WHERE mc.id IS NOT NULL),
                '[]'::json
            ) as missing_certificates,
            COALESCE(
                json_agg(
                    DISTINCT jsonb_build_object(
                        'id', ord.id,
                        'document_type', ord.documenttype,
                        'document_name', ord.documentname
                    )
                ) FILTER (WHERE ord.id IS NOT NULL),
                '[]'::json
            ) as other_documents
        FROM request r
        LEFT JOIN certificate c ON r.id = c.requestid
        LEFT JOIN missingcertificate mc ON r.id = mc.requestid
        LEFT JOIN otherrequireddocument ord ON r.id = ord.requestid
        GROUP BY r.id, r.rfpnumber, r.biddername, r.statuscode, r.summary,
                 r.warningstartdate, r.warningenddate, r.created_date,
                 r.completeddate, r.user_email, r.created_by
    """)

    # Create stored procedure to update certificate by user
    op.execute("""
        CREATE OR REPLACE FUNCTION update_certificate_by_user(
            p_certificate_id UUID,
            p_validation_status VARCHAR,
            p_reason TEXT,
            p_user_email VARCHAR
        )
        RETURNS VOID AS $$
        BEGIN
            UPDATE certificate
            SET
                validation_status = p_validation_status,
                is_manually_validated = TRUE,
                manual_validation_reason = p_reason,
                manually_validated_by = p_user_email,
                manually_validated_at = NOW(),
                updated_date = NOW(),
                updated_by = p_user_email
            WHERE id = p_certificate_id;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Create stored procedure to get certificate request JSON by ID or hash
    op.execute("""
        CREATE OR REPLACE FUNCTION get_cert_request_json_by_id_or_hash(
            p_identifier VARCHAR
        )
        RETURNS JSON AS $$
        DECLARE
            v_request_id UUID;
            v_result JSON;
        BEGIN
            -- Try to find request by ID (if it's a valid UUID)
            BEGIN
                v_request_id := p_identifier::UUID;
            EXCEPTION WHEN OTHERS THEN
                v_request_id := NULL;
            END;

            -- If not a UUID, try to find by file hash
            IF v_request_id IS NULL THEN
                SELECT r.id INTO v_request_id
                FROM request r
                JOIN attachment a ON r.id = a.requestid
                WHERE a.filehash = p_identifier
                LIMIT 1;
            END IF;

            -- Get the full request data as JSON
            IF v_request_id IS NOT NULL THEN
                SELECT row_to_json(vw_requests_detailed)
                INTO v_result
                FROM vw_requests_detailed
                WHERE id = v_request_id;
            END IF;

            RETURN v_result;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """Drop database views and stored procedures."""

    # Drop stored procedures
    op.execute("DROP FUNCTION IF EXISTS get_cert_request_json_by_id_or_hash(VARCHAR)")
    op.execute("DROP FUNCTION IF EXISTS update_certificate_by_user(UUID, VARCHAR, TEXT, VARCHAR)")

    # Drop views
    op.execute("DROP VIEW IF EXISTS vw_requests_detailed")
    op.execute("DROP VIEW IF EXISTS vw_requests_summary")
