"""Certificate embeddings model for vector search."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from datetime import datetime
from uuid import uuid4

from app.config.database import Base


class CertEmbedding(Base):
    """Vector embeddings for semantic certificate search."""

    __tablename__ = "cert_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4, index=True)

    # Foreign keys
    file_id = Column("fileid", UUID(as_uuid=True), index=True)
    request_id = Column(UUID(as_uuid=True), ForeignKey("request.id"), index=True)

    # Content
    content = Column(Text, nullable=False)

    # Metadata
    page_number = Column("pagenumber", Integer)
    language = Column(String(50))
    total_pages = Column("totalpages", Integer)
    bidder_name = Column("biddername", String(500))
    rfp_number = Column("rfpnumber", String(255))

    # Vector embedding (768 dimensions for text-embedding-004)
    embedding = Column(Vector(768))

    def __repr__(self) -> str:
        return f"<CertEmbedding(id={self.id}, page={self.page_number}, file_id={self.file_id})>"
