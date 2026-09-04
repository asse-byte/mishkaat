"""الإشعارات: الحفظ والبثّ الحيّ."""

from datetime import datetime

from app.config import logger
from app.db import db


_sse_clients = {}

async def push_sse_notification(user_id: str, event_type: str, data: dict):
    """
    دفع إشعار SSE حي إلى مستخدم محدد.

    ملاحظة تشغيلية: _sse_clients ذاكرة داخل العملية الواحدة. عند تشغيل uvicorn بأكثر من worker
    لا يصل الإشعار الحي إلا لمن اتصل بنفس العامل — ولهذا يُخزَّن كل إشعار في قاعدة البيانات
    أيضاً (انظر push_notification) فلا يضيع شيء.
    """
    if user_id in _sse_clients:
        for q in _sse_clients[user_id]:
            try:
                await q.put({"event": event_type, "data": data})
            except Exception:
                pass

async def push_notification(user_id: str, event_type: str, title: str, body: str, data: dict = None) -> None:
    """
    [AUDIT-2026-09-03 addition] إشعار مُخزَّن + دفع حيّ.

    كان تنبيه غياب الطالب يُرسَل عبر SSE فقط، أي إلى وليّ أمر متصل بالتطبيق في تلك اللحظة
    بالضبط. ووليّ الأمر في الغالب ليس متصلاً وقت تسجيل الحضور صباحاً، فيضيع التنبيه إلى
    الأبد ولا أثر له في أي مكان. صار كل إشعار يُحفَظ ويمكن قراءته لاحقاً من /api/notifications.
    """
    doc = {
        "user_id": user_id,
        "type": event_type,
        "title": title,
        "body": body,
        "data": data or {},
        "read": False,
        "created_at": datetime.utcnow(),
    }
    try:
        await db.notifications.insert_one(doc)
    except Exception as e:
        logger.error(f"failed to store notification for {user_id}: {e}")
    await push_sse_notification(user_id, event_type, {"title": title, "message": body, **(data or {})})
