"""
المراسلات.

    POST   /api/messages/broadcast          إرسال رسالة
    GET    /api/messages/inbox              الواردة
    GET    /api/messages/broadcasts         الصادرة
    GET    /api/messages/audiences          مَن يجوز لي مراسلته
    POST   /api/messages/{id}/reply         الردّ
    PUT    /api/messages/{id}               تصحيح رسالةٍ أُرسلت
    DELETE /api/messages/{id}               سحبُها
    POST   /api/messages/attachments        رفع وثيقة
    GET    /api/messages/{id}/attachments/{file_id}   تنزيلُها

[قرار المالك 2026-09-07] سلسلةُ المراسلة مغلقة، كلٌّ يخاطب من فوقه ومن تحته
مباشرةً لا غير:

    مدير النظام  ⇄  مدير المركز  ⇄  المعلّم
                        ⇅
                 الطالب / وليّ الأمر

    «مدير النظام لا يتعامل مع أي فرد إلا مدير المركز فقط، لا ينبغي أن يرسل
     الرسالة أو يستقبلها من معلّم أو طالب أو وليّ أمر.»
    «المعلّم يتلقّى الرسائل من مدير المركز فقط ولا غير، ويمكن له إرسال الرسالة
     إلى مدير المركز فقط ولا غير، وحتى الملفّات والوثائق.»
    «من المفيد وجود ميزة يقدر مدير المركز إرسال الرسالة إلى مدير النظام.»

وكان الواقع أبعد من هذا: مدير النظام لا يستطيع إرسال رسالةٍ واحدة (حسابُه بلا
مركز، والشرط يطلب مركزاً فيُردّ بـ400)، ولا يرى واردةً ولا صادرة — وشاشتُه
تعرض له أزرارَ البثّ كاملةً. والمدير لم يكن له سبيلٌ إلى مدير النظام أصلاً.

**الوثائق**: كل رسالةٍ تحمل مرفقات. تُرفع أوّلاً فتُعاد أوصافُها، ثمّ تُرسل مع
الرسالة — أبسط من خلط الحمولة بالملفّ في طلبٍ واحد، ويسمح بالتراجع قبل الإرسال.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile

from app.clock import utcnow
from app.common import safe_object_id, serialize_doc
from app.db import db
from app.files import (
    DOCUMENT_TYPES,
    MAX_DOCUMENT_BYTES,
    delete_file,
    read_file,
    save_upload,
)
from app.models import BulkMessageCreate, ReplyPayload
from app.scope import teacher_record
from app.security import get_current_user

router = APIRouter()

GLOBAL = "global"

# من يجوز له مخاطبة من — مصدرٌ واحد يقرأه الإرسالُ والواجهة معاً، فلا تعرض
# الشاشةُ خياراً يرفضه الخادم.
AUDIENCES: Dict[str, List[Dict[str, str]]] = {
    "admin": [{"value": "center_manager", "label": "مدراء المراكز"}],
    "super_admin": [{"value": "center_manager", "label": "مدراء المراكز"}],
    "center_manager": [
        {"value": "all_teachers", "label": "معلّمو المركز"},
        {"value": "student", "label": "طلاب المركز"},
        {"value": "parent", "label": "أولياء الأمور"},
        {"value": "admin", "label": "إدارة النظام"},
    ],
    "teacher": [{"value": "center_manager", "label": "مدير المركز"}],
    "student": [],
    "parent": [],
}


def _allowed(role: str) -> List[str]:
    return [a["value"] for a in AUDIENCES.get(role, [])]


def _visible_query(current_user: dict) -> Optional[dict]:
    """
    مرشِّح الرسائل التي تصل هذا المستخدم. None تعني «لا شيء».

    يُعاد None لا {} عند فراغ النطاق — المرشِّح الفارغ في مونغو يعني «كل شيء».
    """
    role = current_user["role"]
    cid = current_user.get("center_id")

    if role in ("admin", "super_admin"):
        # لا يصله إلا ما وُجّه إلى إدارة النظام — من مدراء المراكز
        return {"recipient_role": "admin"}

    if role == "center_manager":
        if not cid:
            return None
        return {"$or": [
            {"center_id": cid, "recipient_role": "center_manager"},
            {"center_id": GLOBAL, "recipient_role": "center_manager"},
        ]}

    if not cid:
        return None
    if role == "teacher":
        return {"center_id": cid, "recipient_role": "all_teachers"}
    if role in ("student", "parent"):
        return {"center_id": cid, "recipient_role": role}
    return None


async def _can_see(message: dict, current_user: dict) -> bool:
    """هل تصل هذه الرسالةُ هذا المستخدم، أو هو مُرسِلُها؟"""
    if message.get("sender_id") == str(current_user["_id"]):
        return True
    q = _visible_query(current_user)
    if q is None:
        return False
    found = await db.bulk_messages.find_one({"$and": [{"_id": message["_id"]}, q]})
    return found is not None


@router.get("/api/messages/audiences")
async def my_audiences(current_user: dict = Depends(get_current_user)):
    """الجهاتُ التي يجوز لهذا المستخدم مراسلتُها — تقرؤها الواجهة ولا تُخمّنها."""
    role = current_user["role"]
    return {"audiences": AUDIENCES.get(role, []), "can_send": bool(AUDIENCES.get(role))}


@router.post("/api/messages/attachments")
async def upload_attachment(file: UploadFile = File(...),
                            current_user: dict = Depends(get_current_user)):
    """رفع وثيقةٍ لتُرفَق برسالة. للمُرسِلين وحدهم."""
    if not _allowed(current_user["role"]):
        raise HTTPException(status_code=403, detail="لا تُرسل رسائل من هذا الحساب")
    return await save_upload(
        file, kind="message_attachment",
        center_id=current_user.get("center_id"),
        owner_id=str(current_user["_id"]),
        max_bytes=MAX_DOCUMENT_BYTES, allowed=DOCUMENT_TYPES)


@router.post("/api/messages/broadcast")
async def create_broadcast_message(msg: BulkMessageCreate,
                                   current_user: dict = Depends(get_current_user)):
    """إرسال رسالة إلى جهةٍ مسموحة لهذا الدور."""
    role = current_user["role"]
    allowed = _allowed(role)
    if not allowed:
        raise HTTPException(status_code=403, detail="هذا الحساب يستقبل الرسائل ولا يُرسلها")
    if msg.recipient_role not in allowed:
        raise HTTPException(
            status_code=403,
            detail="لا يجوز مراسلة هذه الجهة من حسابك")

    center_id = current_user.get("center_id")
    if role in ("admin", "super_admin"):
        # حساب إدارة النظام بلا مركز — رسالتُه تصل مدراء المراكز جميعاً.
        # وكان الشرطُ يطلب مركزاً فيُردّ بـ400 ولا يستطيع الإرسال أصلاً.
        center_id = GLOBAL
    elif not center_id:
        raise HTTPException(status_code=400, detail="يجب ربط حسابك بمركز معتمد")

    doc = msg.model_dump()
    doc["center_id"] = center_id
    doc["sender_id"] = str(current_user["_id"])
    doc["sender_name"] = current_user.get("name") or current_user.get("username")
    doc["sender_role"] = role
    doc["sent_at"] = utcnow()
    doc["replies"] = []
    doc["attachments"] = [a.model_dump() for a in (msg.attachments or [])]

    result = await db.bulk_messages.insert_one(doc)
    return serialize_doc({**doc, "_id": result.inserted_id})


@router.get("/api/messages/inbox")
async def get_received_broadcasts(current_user: dict = Depends(get_current_user)):
    """الرسائل الواردة."""
    query = _visible_query(current_user)
    if query is None:
        return []
    rows = await db.bulk_messages.find(query).sort("sent_at", -1).to_list(200)
    return [serialize_doc(m) for m in rows]


@router.get("/api/messages/broadcasts")
async def get_sent_broadcasts(current_user: dict = Depends(get_current_user)):
    """
    الرسائل الصادرة — ما أرسلتُه أنا.

    كان مرشِّحُها المركزَ لا المُرسِل، فيرى مديرُ المركز صادرَ غيره، ويرى مديرُ
    النظام لا شيء (لا مركز له). والصادرُ ما أرسلتَه أنت، لا ما أُرسل من مركزك.
    """
    if not _allowed(current_user["role"]):
        raise HTTPException(status_code=403, detail="غير مصرح")
    rows = await db.bulk_messages.find(
        {"sender_id": str(current_user["_id"])}).sort("sent_at", -1).to_list(200)
    return [serialize_doc(m) for m in rows]


@router.post("/api/messages/{message_id}/reply")
async def reply_to_broadcast(message_id: str, payload: ReplyPayload,
                             current_user: dict = Depends(get_current_user)):
    """الردّ على رسالةٍ واردة — لمن تصله."""
    message = await db.bulk_messages.find_one({"_id": safe_object_id(message_id)})
    if not message:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
    if not await _can_see(message, current_user):
        raise HTTPException(status_code=403, detail="هذه الرسالة ليست لك")
    if current_user["role"] in ("student", "parent"):
        raise HTTPException(
            status_code=403,
            detail="حساب الطالب ووليّ الأمر يستقبل الرسائل ولا يردّ عليها")

    reply = {
        "teacher_id": str(current_user["_id"]),
        "teacher_name": current_user.get("name") or current_user.get("username") or "—",
        "sender_role": current_user["role"],
        "content": payload.content,
        "timestamp": utcnow(),
    }
    await db.bulk_messages.update_one(
        {"_id": message["_id"]}, {"$push": {"replies": reply}})
    updated = await db.bulk_messages.find_one({"_id": message["_id"]})
    return serialize_doc(updated)


@router.put("/api/messages/{message_id}")
async def edit_broadcast(message_id: str, msg: BulkMessageCreate,
                         current_user: dict = Depends(get_current_user)):
    """
    تصحيح رسالةٍ أُرسلت — لمُرسِلها.

    [قرار المالك 2026-09-07] «أيّ عملٍ إداري يقوم به مدير المركز اجعله قابلاً
    للتعديل بعد قيامه به، لأن أيّ عملٍ إداري ممكن يصير فيه خطأ.» والرسالةُ
    المرسَلة بموعدٍ خاطئ كانت لا تُصحَّح ولا تُسحب.
    """
    message = await db.bulk_messages.find_one({"_id": safe_object_id(message_id)})
    if not message:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
    if message.get("sender_id") != str(current_user["_id"]):
        raise HTTPException(status_code=403, detail="تُصحَّح رسالتُك أنت وحدها")

    changes = {
        "subject": msg.subject,
        "content": msg.content,
        "attachments": [a.model_dump() for a in (msg.attachments or [])],
        "edited_at": utcnow(),
    }
    # الجهةُ المستقبِلة لا تتغيّر: تغييرُها يعني رسالةً أخرى وصلت قوماً
    # ثمّ ظهرت لقومٍ غيرهم وقد قرأها الأوّلون.
    await db.bulk_messages.update_one({"_id": message["_id"]}, {"$set": changes})
    return serialize_doc({**message, **changes})


@router.delete("/api/messages/{message_id}")
async def withdraw_broadcast(message_id: str,
                             current_user: dict = Depends(get_current_user)):
    """سحبُ رسالةٍ أُرسلت خطأً — لمُرسِلها أو لإدارة النظام."""
    message = await db.bulk_messages.find_one({"_id": safe_object_id(message_id)})
    if not message:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
    is_owner = message.get("sender_id") == str(current_user["_id"])
    if not is_owner and current_user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="تُسحَب رسالتُك أنت وحدها")

    for att in message.get("attachments") or []:
        if att.get("file_id"):
            await delete_file(att["file_id"])
    await db.bulk_messages.delete_one({"_id": message["_id"]})
    return {"message": "سُحبت الرسالة"}


@router.get("/api/messages/{message_id}/attachments/{file_id}")
async def download_attachment(message_id: str, file_id: str,
                              current_user: dict = Depends(get_current_user)):
    """
    تنزيل وثيقةٍ مرفقة — لمن تصله الرسالة.

    الصلاحية تُفحص على الرسالة لا على الملفّ: معرّفُ الملفّ وحده لو كفى لصار
    من يخمّنه يقرأ وثيقةَ مركزٍ آخر.
    """
    message = await db.bulk_messages.find_one({"_id": safe_object_id(message_id)})
    if not message:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
    if not await _can_see(message, current_user):
        raise HTTPException(status_code=403, detail="هذه الرسالة ليست لك")

    att = next((a for a in (message.get("attachments") or [])
                if a.get("file_id") == file_id), None)
    if not att:
        raise HTTPException(status_code=404, detail="المرفق غير موجود")

    data, meta = await read_file(file_id)
    filename = att.get("filename") or "document"
    return Response(
        content=data,
        media_type=meta.get("content_type", "application/octet-stream"),
        headers={
            # attachment لا inline: الملفّ يُحفظ ولا يُفتح داخل نطاق التطبيق
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
