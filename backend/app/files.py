"""
تخزين الملفات — شعار المركز ومرفقات الرسائل.

لم يكن في النظام رفعُ ملفٍ واحد: لا نقطةَ نهاية تقبل ملفاً، ولا مكانَ تخزين،
ولا طريقَ تقديم. وطلبَ المالك أمرين يحتاجان إليه معاً: شعارُ المركز يظهر على
الشهادات والفواتير، وتبادلُ الوثائق بين المدير والمعلّم. فبُني هنا مرّةً
واحدة ليخدمهما.

**لماذا GridFS لا مجلّدٌ على القرص؟** لأن النظام يُنشر في حاويةٍ يذهب قرصُها
مع كل إصدار، فمجلّدُ رفعٍ بلا وحدة تخزينٍ دائمة يعني شعاراً يختفي عند أوّل
تحديث. والملفّات هنا صغيرة ومعدودة (شعارٌ للمركز، ووثائقُ مراسلة)، ونسخةُ
قاعدة البيانات الاحتياطية تحملها معها بلا إجراءٍ ثانٍ.

**النوع يُعرف من محتوى الملفّ لا من ترويسته.** `content_type` نصٌّ يكتبه
المتصفّح ويستطيع المرسِل تزويره، فملفٌّ تنفيذيّ يُرسَل موسوماً بأنه صورة.
فتُقرأ البصمة الأولى من البايتات نفسها، ويُرفض ما لا يطابق.

**ولا SVG.** هو مستندٌ يحمل نصّاً برمجياً، وعرضُه من نطاق التطبيق يفتح
ثغرةَ حقنٍ في صفحةٍ يملكها المستخدم. والشعار يُقبل PNG و JPEG و WEBP.
"""

from typing import Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException, UploadFile
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from app.clock import utcnow
from app.db import db

BUCKET = "files"

# حدودٌ ضيّقة عن قصد: nginx يقف عند 8 ميغابايت، والتطبيق أضيق منه.
MAX_LOGO_BYTES = 512 * 1024          # نصف ميغابايت — شعارٌ للطباعة لا صورةُ كاميرا
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024  # خمسة ميغابايت للوثيقة الواحدة

IMAGE_TYPES = ("image/png", "image/jpeg", "image/webp")
DOCUMENT_TYPES = IMAGE_TYPES + ("application/pdf",)


def _sniff(head: bytes) -> Optional[str]:
    """نوعُ الملفّ من بصمته الأولى، أو None إن لم يُعرف."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _bucket() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(db, bucket_name=BUCKET)


async def save_upload(
    upload: UploadFile,
    *,
    kind: str,
    center_id: Optional[str],
    owner_id: str,
    max_bytes: int,
    allowed: Tuple[str, ...],
) -> dict:
    """
    يقرأ الملفّ ويتحقّق منه ويخزّنه، ويُعيد وصفَه.

    القراءة على دفعات بسقفٍ صارم: قراءةُ الملفّ كاملاً ثمّ قياسُه تعني أن
    مُرسِلاً واحداً يستطيع أن يُحمّل الخادمَ ما شاء قبل أن يُردّ.
    """
    chunks = []
    total = 0
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"حجم الملفّ يتجاوز الحدّ المسموح ({max_bytes // 1024} كيلوبايت)")
        chunks.append(chunk)

    data = b"".join(chunks)
    if not data:
        raise HTTPException(status_code=400, detail="الملفّ فارغ")

    sniffed = _sniff(data[:16])
    if sniffed is None or sniffed not in allowed:
        names = "، ".join(t.split("/")[-1].upper() for t in allowed)
        raise HTTPException(
            status_code=400,
            detail=f"نوع الملفّ غير مقبول — المسموح: {names}")

    name = (upload.filename or "file")[:120]
    file_id = await _bucket().upload_from_stream(
        name,
        data,
        metadata={
            "kind": kind,
            "center_id": center_id,
            "owner_id": owner_id,
            "content_type": sniffed,   # المُستنتَج لا المُرسَل
            "size": total,
            "uploaded_at": utcnow(),
        },
    )
    return {
        "file_id": str(file_id),
        "filename": name,
        "content_type": sniffed,
        "size": total,
    }


async def read_file(file_id: str) -> Tuple[bytes, dict]:
    """محتوى الملفّ ووصفُه. يرفع 404 إن لم يوجد."""
    try:
        oid = ObjectId(file_id)
    except Exception:
        raise HTTPException(status_code=404, detail="الملفّ غير موجود")
    try:
        stream = await _bucket().open_download_stream(oid)
    except Exception:
        raise HTTPException(status_code=404, detail="الملفّ غير موجود")
    data = await stream.read()
    meta = stream.metadata or {}
    meta.setdefault("filename", stream.filename)
    return data, meta


async def delete_file(file_id: str) -> None:
    """حذفٌ صامت: ملفٌّ ذهب مسبقاً ليس خطأً يُبلَّغ به المستخدم."""
    try:
        await _bucket().delete(ObjectId(file_id))
    except Exception:
        pass
