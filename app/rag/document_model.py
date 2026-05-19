import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class DocType(str, enum.Enum):
    pdf = "pdf"
    text = "text"
    docx = "docx"
    xlsx = "xlsx"
    csv = "csv"
    markdown = "markdown"
    url = "url"


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("user_id", "source", name="uq_documents_user_source"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String, index=True)
    filename: Mapped[str] = mapped_column(String)
    type: Mapped[DocType] = mapped_column(SAEnum(DocType, name="doctype"))
    chunk_count: Mapped[int] = mapped_column(Integer)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
