"""
ORM model for the ``reports_log`` table.

Tracks every PDF report generation attempt — both scheduled and on-demand.
Used by the reports router to list history and surface download links.
"""

from __future__ import annotations

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.shipment import Base


class ReportLog(Base):
    """One row per PDF generation attempt.

    Lifecycle
    ---------
    1. Row inserted with ``status='pending'`` before background task starts.
    2. Background task updates to ``status='success'`` + ``s3_path`` on
       completion, or ``status='failed'`` + ``error_message`` on exception.

    The ``week`` column stores the ISO-8601 week string, e.g. ``"2025-W14"``.
    """

    __tablename__ = "reports_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ISO week string: "YYYY-Www"
    week: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    generated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # S3 key set after successful upload, e.g. "reports/weekly_report_2025-W14.pdf"
    s3_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # pending | success | failed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    # File size in bytes (set after upload)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Human-readable error if status='failed'
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ReportLog id={self.id} week={self.week!r} "
            f"status={self.status!r}>"
        )
