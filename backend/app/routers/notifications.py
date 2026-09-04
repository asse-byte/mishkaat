"""الإشعارات."""

from app.clock import utcnow

from datetime import datetime
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi.responses import StreamingResponse
import asyncio
import json

from app.common import safe_object_id, serialize_doc
from app.config import logger
from app.db import db
from app.security import get_current_user
from app.sse import consume_stream_ticket, issue_stream_ticket

router = APIRouter()


@router.get("/api/notifications")
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """إشعارات المستخدم الحالي فقط"""
    query: dict = {"user_id": str(current_user["_id"])}
    if unread_only:
        query["read"] = False

    rows = await db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    unread = await db.notifications.count_documents({"user_id": str(current_user["_id"]), "read": False})
    items = []
    for n in rows:
        doc = serialize_doc(n)
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        items.append(doc)
    return {"items": items, "unread_count": unread}

@router.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    """تعليم إشعار كمقروء — لصاحبه وحده"""
    result = await db.notifications.update_one(
        {"_id": safe_object_id(notification_id), "user_id": str(current_user["_id"])},
        {"$set": {"read": True, "read_at": utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="الإشعار غير موجود")
    return {"message": "تم"}

@router.post("/api/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    result = await db.notifications.update_many(
        {"user_id": str(current_user["_id"]), "read": False},
        {"$set": {"read": True, "read_at": utcnow()}},
    )
    return {"message": "تم", "updated": result.modified_count}

@router.post("/api/notifications/stream-ticket")
async def create_stream_ticket(current_user: dict = Depends(get_current_user)):
    """
    [إصلاح 2026-09-04] تذكرة قصيرة العمر لفتح قناة البثّ.

    تُطلب برأس Authorization عادي — فلا يمرّ توكن الوصول في مسار الرابط ولا
    يتسرّب إلى سجلّات nginx ولا إلى تاريخ المتصفّح.
    """
    return await issue_stream_ticket(str(current_user["_id"]))


@router.get("/api/notifications/stream")
async def sse_notifications_stream(request: Request, ticket: str):
    """
    قناة SSE لاستلام الإشعارات الفورية.

    [إصلاح 2026-09-04] مصدر الأحداث صار قاعدة البيانات لا طابوراً في الذاكرة.
    النسخة السابقة كانت تقرأ من _sse_clients، وهي ذاكرة داخل العامل الواحد: مع
    UVICORN_WORKERS=4 لا يصل الإشعار إلا لمن اتّصل بالعامل الذي كتبه. الآن تُستطلَع
    مجموعة الإشعارات كل ثانيتين، فيصل ما كتبه أي عامل إلى أي عميل، بلا Redis ولا
    اعتماد جديد. والتأخير الأقصى ثانيتان — مقبول لتنبيه غياب.
    """
    user_id = await consume_stream_ticket(ticket)
    if not user_id:
        raise HTTPException(status_code=401, detail="تذكرة البثّ غير صالحة أو منتهية")

    # لا تُعاد الإشعارات القديمة عند كل اتصال — نبدأ من لحظة الفتح
    since = utcnow()
    POLL_SECONDS = 2.0
    KEEPALIVE_EVERY = 15.0

    async def generator():
        nonlocal since
        idle = 0.0
        while True:
            if await request.is_disconnected():
                break
            try:
                cursor = db.notifications.find(
                    {"user_id": user_id, "created_at": {"$gt": since}}
                ).sort("created_at", 1).limit(50)
                sent = False
                async for n in cursor:
                    since = n["created_at"]
                    payload = {"title": n.get("title"), "message": n.get("body"), **(n.get("data") or {})}
                    yield (f"event: {n.get('type', 'notification')}" \
                           f"\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n")
                    sent = True
                if sent:
                    idle = 0.0
            except Exception as e:
                logger.error(f"SSE poll failed for {user_id}: {e}")

            await asyncio.sleep(POLL_SECONDS)
            idle += POLL_SECONDS
            if idle >= KEEPALIVE_EVERY:
                idle = 0.0
                yield ": keep-alive\n\n"

    # [إصلاح 2026-09-03 — اكتُشف في مراجعة الإصلاحات نفسها]
    # استيراد asyncio أزال الانهيار، لكن القناة ظلت لا تُوصِّل شيئاً: العميل يتصل ويُسجَّل
    # ويعود 200، ولا يصل أي حدث. سببان يخنقان البثّ، كلاهما يجمّع الاستجابة قبل إرسالها:
    #   1) GZipMiddleware يضغط الجسم فيحتجزه — و Starlette يتخطّاه إن كان الرأس Content-Encoding
    #      مضبوطاً مسبقاً، فنضبطه إلى identity (أي بلا تحويل).
    #   2) nginx يضبط proxy_buffering on لكل مسارات /api، و X-Accel-Buffering: no يلغيه
    #      لهذه الاستجابة وحدها فتبقى بقية الواجهة مستفيدة من التخزين المؤقت.
    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Content-Encoding": "identity",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
