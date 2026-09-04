"""فحص الصحّة والجاهزية."""

from datetime import datetime
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import APP_VERSION, IS_PRODUCTION, logger
from app.db import db

router = APIRouter()


# ==================== Health Check ====================

@router.get("/api/health")
async def health_check():
    """فحص صحة النظام"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@router.get("/api/health/ready")
async def readiness_check():
    """
    [AUDIT-2026-09-03 addition] فحص جاهزية حقيقي.
    /api/health كان يجيب "سليم" حتى وقاعدة البيانات ساقطة تماماً، فلا يكشف عطلاً ولا يصلح
    لموازِن حِمل أو لمراقبة. هذا الفحص يلمس قاعدة البيانات فعلاً ويعيد 503 عند فشلها.
    """
    try:
        await db.command("ping")
    except Exception as e:
        logger.error(f"readiness probe failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": False, "timestamp": datetime.utcnow().isoformat()},
        )
    return {
        "status": "ready",
        "database": True,
        "environment": "production" if IS_PRODUCTION else "development",
        "version": APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
    }
