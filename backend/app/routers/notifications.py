"""الإشعارات."""

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
from app.db import db
from app.security import _decode_and_verify, get_current_user
from app.sse import _sse_clients

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
        {"$set": {"read": True, "read_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="الإشعار غير موجود")
    return {"message": "تم"}

@router.post("/api/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    result = await db.notifications.update_many(
        {"user_id": str(current_user["_id"]), "read": False},
        {"$set": {"read": True, "read_at": datetime.utcnow()}},
    )
    return {"message": "تم", "updated": result.modified_count}

@router.get("/api/notifications/stream")
async def sse_notifications_stream(token: str, request: Request):
    """قناة SSE لاستلام الإشعارات الفورية"""
    try:
        payload, user = await _decode_and_verify(token, expected_type="access")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    user_id = str(user["_id"])
    
    q = asyncio.Queue()
    if user_id not in _sse_clients:
        _sse_clients[user_id] = set()
    _sse_clients[user_id].add(q)
    
    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event_data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"event: {event_data['event']}\ndata: {json.dumps(event_data['data'])}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            if user_id in _sse_clients:
                _sse_clients[user_id].discard(q)
                if not _sse_clients[user_id]:
                    del _sse_clients[user_id]
                    
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
