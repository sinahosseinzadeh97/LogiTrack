# backend/app/models/__init__.py
#
# Auth models (User, TokenBlacklist) are defined in app.auth.models and share
# the same Base declared in app.models.shipment.  They register themselves with
# Base.metadata when app.auth.models is imported (which happens at startup via
# app.auth.router and app.main).  We do NOT import them here to avoid a
# circular-import cycle:
#
#   app.auth.models → app.models.shipment (Base)
#   app.models.__init__ → app.auth.models   ← cycle
#
from .report_log import ReportLog
from .shipment import Base, KpiDaily, MlModelVersion, SellerStats, Shipment

__all__ = [
    "Base",
    "Shipment",
    "KpiDaily",
    "SellerStats",
    "MlModelVersion",
    "ReportLog",
]

