"""الإشعارات: الحفظ والبثّ الحيّ."""

import secrets

from app.clock import utcnow
from app.config import logger
from app.db import db

# عمر تذكرة البثّ. قصير عمداً: التذكرة تمرّ في مسار الرابط، وكل ما يمرّ هناك
# يُسجَّل في nginx وفي تاريخ المتصفّح. دقيقة تكفي لفتح القناة فور طلبها.
STREAM_TICKET_TTL_SECONDS = 60


async def issue_stream_ticket(user_id: str) -> dict:
    """
    [إصلاح 2026-09-04] تذكرة بديلة عن تمرير توكن الوصول في مسار الرابط.

    كانت القناة تُفتح بـ ?token=<access_token>، وEventSource لا يرسل رؤوساً فلم يكن
    أمامها غير ذلك. لكن الرابط يُسجَّل كاملاً في سجلّات nginx وفي تاريخ المتصفّح
    وفي رأس Referer، فيتسرّب توكن صالح لساعة كاملة إلى أماكن لا تُحرَس.

    التذكرة تحلّ هذا: تُطلَب برأس Authorization عادي، وتعيش دقيقة واحدة،
    وتُستهلَك مرة واحدة فقط (find_one_and_delete ذرّي، فلا تُقبل مرتين حتى لو
    وصلت طلبان معاً).
    """
    ticket = secrets.token_urlsafe(32)
    await db.stream_tickets.insert_one({
        "ticket": ticket,
        "user_id": user_id,
        "created_at": utcnow(),
        "expires_at": utcnow().timestamp() + STREAM_TICKET_TTL_SECONDS,
    })
    return {"ticket": ticket, "expires_in": STREAM_TICKET_TTL_SECONDS}


async def consume_stream_ticket(ticket: str) -> str | None:
    """يستهلك التذكرة مرة واحدة ويعيد صاحبها، أو None إن كانت باطلة أو منتهية."""
    if not ticket:
        return None
    doc = await db.stream_tickets.find_one_and_delete({"ticket": ticket})
    if not doc:
        return None
    if float(doc.get("expires_at", 0)) < utcnow().timestamp():
        return None
    return doc.get("user_id")


async def push_notification(user_id: str, event_type: str, title: str, body: str, data: dict = None) -> None:
    """
    [AUDIT-2026-09-03 addition] إشعار مُخزَّن.

    كان تنبيه غياب الطالب يُرسَل عبر SSE فقط، أي إلى وليّ أمر متصل بالتطبيق في تلك اللحظة
    بالضبط. ووليّ الأمر في الغالب ليس متصلاً وقت تسجيل الحضور صباحاً، فيضيع التنبيه إلى
    الأبد ولا أثر له في أي مكان. صار كل إشعار يُحفَظ ويمكن قراءته لاحقاً من /api/notifications.

    [إصلاح 2026-09-04] لم يعد هنا دفعٌ إلى طوابير داخل العملية.
    كانت النسخة السابقة تُوزّع على _sse_clients، وهي ذاكرة داخل العامل الواحد: مع
    UVICORN_WORKERS=4 لا يصل الإشعار إلا لمن اتّصل صدفةً بالعامل الذي كتبه — أي رُبع
    الحالات. صارت قاعدة البيانات هي مصدر البثّ الوحيد، وقناة البثّ تقرأ منها، فيصل
    الإشعار من أي عامل إلى أي عامل بلا وسيط ولا اعتماد جديد.
    """
    doc = {
        "user_id": user_id,
        "type": event_type,
        "title": title,
        "body": body,
        "data": data or {},
        "read": False,
        "created_at": utcnow(),
    }
    try:
        await db.notifications.insert_one(doc)
    except Exception as e:
        logger.error(f"failed to store notification for {user_id}: {e}")
