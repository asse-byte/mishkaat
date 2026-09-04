"""سجل التدقيق."""

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi.responses import JSONResponse
from typing import Optional
import hashlib

from app.audit import audit_hash_input
from app.common import parse_date_boundary, serialize_doc
from app.db import db
from app.security import get_current_user

router = APIRouter()


@router.get("/api/audit-logs")
async def get_audit_logs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    action: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    """سجل النشاط - للمدير فقط"""
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول")

    query: dict = {}
    if current_user["role"] != "super_admin":
        user_cid = current_user.get("center_id")
        if not user_cid:
            # مدير نظام غير مرتبط بمركز: يرى الأحداث العامة (دخول/خروج/تعديل صلاحيات)
            query["center_id"] = "system"
        else:
            query["center_id"] = user_cid

    if action:
        query["action"] = action

    date_range = {}
    if from_date:
        parsed = parse_date_boundary(from_date, end=False)
        if parsed:
            date_range["$gte"] = parsed
    if to_date:
        parsed = parse_date_boundary(to_date, end=True)
        if parsed:
            date_range["$lte"] = parsed
    if date_range:
        query["timestamp"] = date_range

    total = await db.audit_logs.count_documents(query)
    logs = await db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    items = [serialize_doc(log) for log in logs]
    # [AUDIT-2026-09-03 addition: العدّاد الكلي حتى يعرف الترقيم في الواجهة أين يتوقف]
    return JSONResponse(
        content=jsonable_encoder(items),
        headers={"X-Total-Count": str(total), "Access-Control-Expose-Headers": "X-Total-Count"},
    )

@router.get("/api/audit-logs/verify")
async def verify_audit_chain(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(5000, ge=1, le=50000),
):
    """
    [AUDIT-2026-09-03 addition] التحقق الفعلي من سلامة سلسلة سجل التدقيق.

    كانت البصمات تُحسب وتُخزَّن ولا يقرؤها أحد قط — أي سلسلة بلا مدقِّق لا تحمي شيئاً.
    هذه النقطة تعيد بناء بصمة كل سجل وتقارنها بالمخزَّن وتتحقق من ترابط previous_hash،
    فتكشف أي تعديل أو حذف لسجل مالي بعد كتابته.
    """
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    entries = await db.audit_logs.find(
        {"seq": {"$ne": None}}
    ).sort("seq", 1).limit(limit).to_list(limit)

    broken_hash, broken_link, gaps = [], [], []
    previous = None
    checked = 0

    for e in entries:
        checked += 1
        expected = hashlib.sha256(audit_hash_input(e).encode()).hexdigest()
        if expected != e.get("log_hash"):
            broken_hash.append({"seq": e.get("seq"), "action": e.get("action")})
        if previous is not None:
            if e.get("seq") != previous.get("seq", 0) + 1:
                gaps.append({"after_seq": previous.get("seq"), "next_seq": e.get("seq")})
            elif e.get("previous_hash") != previous.get("log_hash"):
                broken_link.append({"seq": e.get("seq"), "action": e.get("action")})
        if e.get("chain_gap"):
            gaps.append({"marked_gap_at_seq": e.get("seq")})
        previous = e

    legacy = await db.audit_logs.count_documents({"seq": None})
    intact = not broken_hash and not broken_link and not gaps

    return {
        "intact": intact,
        "entries_checked": checked,
        "legacy_unchained_entries": legacy,
        "tampered_entries": broken_hash,
        "broken_links": broken_link,
        "sequence_gaps": gaps,
        "message": "السلسلة سليمة ولم يُعدَّل أي سجل" if intact else "تم رصد خلل في سلسلة سجل التدقيق — راجع التفاصيل",
    }
