"""
Reports router — /api/v1/reports prefix.

Endpoints
---------
POST /api/v1/reports/generate
    Requires analyst role.  Triggers WeeklyReportGenerator as a BackgroundTask.
    Saves PDF to S3 as ``reports/weekly_report_{YYYY-WW}.pdf``.
    Saves report metadata to ``reports_log`` table.
    Returns: {message: str, report_id: int}

GET /api/v1/reports
    Returns list of generated reports from ``reports_log``.
    Columns: id, week, generated_at, s3_path, status, file_size_bytes.
    Requires viewer role.

GET /api/v1/reports/{report_id}/download
    Generates a presigned S3 URL valid for 15 minutes.
    Redirects to that URL.
    Requires viewer role.

GET /api/v1/reports/{report_id}/preview
    Returns first 3 pages as base64-encoded PNG thumbnails via pdf2image.
    Requires viewer role.
"""

from __future__ import annotations

import base64
import io
import logging
from datetime import date, datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import ANALYST_AND_ABOVE, VIEWER_AND_ABOVE, require_role
from app.config import get_settings
from app.database import get_async_session, sync_engine
from app.models.report_log import ReportLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["Reports"])

_ViewerDep  = Annotated[User, Depends(require_role(*VIEWER_AND_ABOVE))]
_AnalystDep = Annotated[User, Depends(require_role(*ANALYST_AND_ABOVE))]


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class ReportItem(BaseModel):
    """Single entry from ``reports_log``."""

    id: int
    week: str
    generated_at: datetime
    s3_path: str | None
    status: str
    file_size_bytes: int | None

    model_config = {"from_attributes": True}


class GenerateResponse(BaseModel):
    message: str
    report_id: int


class PreviewResponse(BaseModel):
    report_id: int
    pages: list[str]  # base64-encoded PNG per page


# ---------------------------------------------------------------------------
# Background task — generates PDF, uploads to S3, updates DB row
# ---------------------------------------------------------------------------


def _run_report_generation(report_id: int, week_date: date) -> None:
    """Synchronous PDF generation task executed in a background thread.

    All DB access here uses the *sync* engine so we can safely call
    blocking libraries (ReportLab, Plotly/kaleido, boto3) without an
    async context.
    """
    from sqlalchemy.orm import Session

    import boto3  # type: ignore[import-untyped]

    from app.database import SyncSessionLocal
    from app.models.report_log import ReportLog
    from reports.report_gen import WeeklyReportGenerator, generate_with_dark_cover

    settings = get_settings()

    # Build the boto3 S3 client
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )

    with SyncSessionLocal() as db:
        # ── Generate PDF ────────────────────────────────────────────────────
        try:
            generator = WeeklyReportGenerator(
                db_engine=sync_engine,
                s3_client=s3,
                week=week_date,
            )
            pdf_bytes = generate_with_dark_cover(generator)

            iso_label = generator.iso_week_label
            s3_key    = f"reports/weekly_report_{iso_label}.pdf"

            # ── Upload to S3 ────────────────────────────────────────────────
            s3.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=s3_key,
                Body=pdf_bytes,
                ContentType="application/pdf",
            )

            file_size = len(pdf_bytes)

            # ── Update DB row ───────────────────────────────────────────────
            report: ReportLog | None = db.get(ReportLog, report_id)
            if report:
                report.status          = "success"
                report.s3_path         = s3_key
                report.file_size_bytes = file_size
                db.commit()

            logger.info(
                "Report %d generated successfully — key=%s size=%d bytes",
                report_id, s3_key, file_size,
            )

        except Exception as exc:  # noqa: BLE001
            logger.error("Report %d generation FAILED: %s", report_id, exc)
            try:
                report = db.get(ReportLog, report_id)
                if report:
                    report.status        = "failed"
                    report.error_message = str(exc)[:2000]
                    db.commit()
            except Exception as inner:  # noqa: BLE001
                logger.error("Could not update report status: %s", inner)


# ---------------------------------------------------------------------------
# POST /api/v1/reports/generate
# ---------------------------------------------------------------------------


@router.post(
    "/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger weekly PDF report generation",
)
async def generate_report(
    _: _AnalystDep,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> GenerateResponse:
    """Enqueue a PDF generation task for the current ISO week.

    The task runs asynchronously; the response returns immediately with
    the ``report_id`` that can be polled via ``GET /api/v1/reports``.
    """
    # Use the latest available data week from the dataset, not today's calendar date.
    # The Olist dataset only has data through ~2018-08, so using date.today()
    # (2026) would produce an empty report.
    try:
        latest = await db.execute(text("SELECT MAX(date) FROM kpi_daily"))
        max_date = latest.scalar()
        week = max_date if max_date is not None else date.today()
    except Exception:
        week = date.today()

    # Compute ISO week label for display
    from datetime import timedelta
    week_monday = week - timedelta(days=week.isoweekday() - 1)
    iso_cal   = week_monday.isocalendar()
    week_label = f"{iso_cal.year}-W{iso_cal.week:02d}"

    # Insert pending row
    new_report = ReportLog(
        week=week_label,
        status="pending",
    )
    db.add(new_report)
    await db.flush()
    await db.refresh(new_report)
    report_id = new_report.id
    await db.commit()

    # Enqueue background task
    background_tasks.add_task(_run_report_generation, report_id, week)

    logger.info("Report generation enqueued — report_id=%d week=%s", report_id, week_label)
    return GenerateResponse(
        message=f"Report generation started for week {week_label}.",
        report_id=report_id,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/reports
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[ReportItem],
    summary="List all generated reports",
)
async def list_reports(
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> list[ReportItem]:
    """Return all rows from ``reports_log``, newest first."""
    result = await db.execute(
        select(ReportLog).order_by(ReportLog.generated_at.desc())
    )
    rows = result.scalars().all()
    return [ReportItem.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/v1/reports/{report_id}/download
# ---------------------------------------------------------------------------


@router.get(
    "/{report_id}/download",
    summary="Get a presigned S3 download URL (15 min expiry)",
)
async def download_report(
    report_id: int,
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> RedirectResponse:
    """Generate a presigned S3 URL and redirect the client to it."""
    import boto3

    report: ReportLog | None = await db.get(ReportLog, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    if report.status != "success" or not report.s3_path:
        raise HTTPException(
            status_code=409,
            detail=f"Report is not available (status={report.status!r}).",
        )

    settings = get_settings()
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )

    presigned_url: str = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": report.s3_path},
        ExpiresIn=900,  # 15 minutes
    )
    return RedirectResponse(url=presigned_url, status_code=307)


# ---------------------------------------------------------------------------
# GET /api/v1/reports/{report_id}/preview
# ---------------------------------------------------------------------------


@router.get(
    "/{report_id}/preview",
    response_model=PreviewResponse,
    summary="Return first 3 pages of a report as base64 PNG thumbnails",
)
async def preview_report(
    report_id: int,
    _: _ViewerDep,
    db: Annotated[AsyncSession, Depends(get_async_session)],
) -> PreviewResponse:
    """Download the PDF from S3 and convert the first 3 pages to PNG.

    Uses ``pdf2image`` (wkhtmltopdf-free; requires ``poppler`` at the OS level
    and the ``pdf2image`` Python package).
    """
    import boto3

    report: ReportLog | None = await db.get(ReportLog, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    if report.status != "success" or not report.s3_path:
        raise HTTPException(
            status_code=409,
            detail=f"Report not available for preview (status={report.status!r}).",
        )

    settings = get_settings()
    s3 = boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )

    # Download PDF bytes
    response: Any = s3.get_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=report.s3_path,
    )
    pdf_bytes: bytes = response["Body"].read()

    # Convert first 3 pages to PNG
    try:
        from pdf2image import convert_from_bytes  # type: ignore[import-untyped]

        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=3, dpi=120)
        pages: list[str] = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            pages.append(base64.b64encode(buf.getvalue()).decode())

    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="pdf2image is not installed. Install poppler and pdf2image>=1.17.0.",
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Preview conversion failed for report %d: %s", report_id, exc)
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {exc}")

    return PreviewResponse(report_id=report_id, pages=pages)
