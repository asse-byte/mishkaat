"""تركيب التطبيق: دورة الحياة، الوسائط، وضمّ الموجّهات."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import uuid

from app.config import ALLOWED_ORIGINS, APP_VERSION, IS_PRODUCTION, logger
from app.startup import startup_event
from app.routers import (
    attendance, audit_logs, auth, centers, competitions, dashboard, exports,
    finance, halaqat, health, messages, notifications, performance, recitations,
    review_plans, schedules, students, teachers,
)

# ترتيب الضمّ مقصود: الموجّهات ذات المسارات الثابتة قبل التي تحمل معاملات في
# المسار، حتى لا يبتلع /api/centers/{id} مسارَ /api/centers/pending.
ROUTERS = (
    auth.router,
    audit_logs.router,
    notifications.router,
    dashboard.router,
    centers.router,
    students.router,
    teachers.router,
    halaqat.router,
    schedules.router,
    competitions.router,
    messages.router,
    recitations.router,
    performance.router,
    attendance.router,
    finance.router,
    review_plans.router,
    exports.router,
    health.router,
)


# [AUDIT-2026-09-03 fix: @app.on_event("startup") مهجور وسيُحذف من FastAPI.
#  الدالة startup_event نفسها لم تتغير — غيّرنا طريقة استدعائها فقط، والاختبارات تناديها مباشرة.]
@asynccontextmanager
async def lifespan(_app: FastAPI):
    await startup_event()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="نظام إدارة مراكز التحفيظ",
    description="API لإدارة مراكز تحفيظ القرآن الكريم",
    version=APP_VERSION,
    # الوثائق التفاعلية متاحة في التطوير فقط، ومعطّلة تماماً في الإنتاج
    docs_url=None if IS_PRODUCTION else "/api/docs",
    redoc_url=None,
    openapi_url=None if IS_PRODUCTION else "/api/openapi.json",
)

# GZip compression لتسريع الاستجابات
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=600,
)


# [AUDIT-2026-09-03 addition: رؤوس أمنية على كل استجابة + معرّف طلب للتتبّع]
@app.middleware("http")
async def security_and_tracing_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except HTTPException:
        raise
    except Exception:
        # [AUDIT-2026-09-03 fix: لا تُسرّب أثر الاستثناء (stack trace) للعميل — يُسجَّل داخلياً فقط]
        logger.exception(f"[{request_id}] unhandled error on {request.method} {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={"detail": "حدث خطأ داخلي في الخادم", "request_id": request_id},
        )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # واجهة JSON فقط: لا سكربتات ولا إطارات (ما عدا صفحة الوثائق في التطوير)
    if not request.url.path.startswith("/api/docs"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


for _router in ROUTERS:
    app.include_router(_router)
