"""
الشهادات — يُصدرها مدير المركز.

    GET    /api/certificates              الشهادات المُصدَرة (كلٌّ في نطاقه)
    GET    /api/certificates/eligible     من استحقّ محطّةً ولم تُصدَر له بعد
    POST   /api/certificates/milestone    شهادة حفظٍ (5، 10، نصف، ختم)
    POST   /api/certificates/competition/{contestant_id}   شهادة مسابقة
    DELETE /api/certificates/{id}         إلغاء شهادةٍ أُصدرت خطأً

[قرار المالك 2026-09-07] «مدير المركز هو الذي يصدر الشهادة للطالب وليس المعلّم.
بعدما تقوم اللجنة بإدخال الدرجات، يعتمدها المدير ثمّ يُصدر الشهادة. وحتى بعد
ختم الطالب للقرآن مباشرة يظهر إصدار الشهادة للحافظ، وكذلك بعد نصف القرآن.»

ثلاثة أشياء تُميّز هذا عن زرّ طباعة:

    1. **الإصدار فعلٌ يُسجَّل**: رقمٌ متسلسل، ومَن أصدره، ومتى. فالشهادة التي
       يُشكَّك فيها تُراجَع في السجلّ.
    2. **لا تُصدَر مرّتين**: فهرسٌ فريد يمنع شهادتين لنفس المحطّة لنفس الطالب.
    3. **لا تُصدَر قبل استحقاقها**: شهادة المسابقة تنتظر اعتماد النتائج،
       وشهادة الحفظ تُقاس على ما سُمِّع فعلاً لا على ما يُقال.

والطالب ووليّه يريان شهاداتهما ويطبعانها — الإصدار وحده للمدير.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.audit import write_audit_log
from app.clock import utcnow
from app.common import NOT_DELETED, check_student_access, safe_object_id, serialize_doc
from app.config import TOTAL_QURAN_PAGES
from app.db import db
from app.metrics import compute_all
from app.models import MILESTONES, MilestoneCertificateCreate
from app.scope import student_query, visible_student_ids
from app.security import get_current_user

router = APIRouter(tags=["الشهادات"])

MANAGERS = ("admin", "super_admin", "center_manager")
PAGES_PER_JUZ = TOTAL_QURAN_PAGES / 30.0


def _require_manager(current_user: dict) -> None:
    if current_user["role"] not in MANAGERS:
        raise HTTPException(
            status_code=403,
            detail="إصدار الشهادات من عمل مدير المركز — المعلّم يُسمّع ويُقيّم ولا يُصدر")


async def _pages_memorized(student_id: str) -> float:
    """الصفحات المحفوظة من واقع التسميع — لا من حقلٍ يُكتب باليد."""
    recs = await db.recitations.find(
        {**NOT_DELETED, "student_id": student_id}).to_list(5000)
    return compute_all(recs, []).get("pages_memorized") or 0.0


async def _next_serial(center_id: str) -> str:
    """
    رقمٌ متسلسل لكل مركزٍ وسنة: MK-<سنة>-<تسلسل>.

    عدّادٌ ذرّي في مونغو لا `count_documents() + 1`: الثاني يُعطي رقمين
    متطابقين لإصدارين متزامنين، وهو بالضبط ما يقع في يوم التكريم.
    """
    year = utcnow().year
    key = f"cert:{center_id}:{year}"
    doc = await db.counters.find_one_and_update(
        {"_id": key}, {"$inc": {"seq": 1}}, upsert=True, return_document=True)
    seq = (doc or {}).get("seq", 1)
    return f"MK-{year}-{seq:05d}"


async def _center_name(center_id: Optional[str]) -> Optional[str]:
    if not center_id:
        return None
    c = await db.centers.find_one({"_id": safe_object_id(center_id)}, {"name": 1})
    return (c or {}).get("name")


def _shape(doc: dict) -> dict:
    d = serialize_doc(doc)
    d.setdefault("judges_names", [])
    return d


# ------------------------------------------------------------------ القراءة
@router.get("/api/certificates")
async def list_certificates(student_id: Optional[str] = None,
                            current_user: dict = Depends(get_current_user)):
    """
    الشهادات في نطاق المستخدم.

    المدير: مركزُه. المحفّظ: طلاب حلقاته. الطالب ووليّه: شهاداتُه هو.
    """
    query: dict = {}
    role = current_user["role"]

    if role in ("admin", "super_admin"):
        pass
    elif role == "center_manager":
        cid = current_user.get("center_id")
        if not cid:
            return []
        query["center_id"] = cid
    else:
        ids = await visible_student_ids(current_user)
        if not ids:
            return []
        query["student_id"] = {"$in": ids}

    if student_id:
        await check_student_access(student_id, current_user)
        query["student_id"] = student_id

    rows = await db.certificates.find(query).sort("issued_at", -1).to_list(500)
    return [_shape(r) for r in rows]


@router.get("/api/certificates/eligible")
async def eligible_students(current_user: dict = Depends(get_current_user)):
    """
    من بلغ محطّةً ولم تُصدَر له شهادتُها.

    هذا ما يجعل «بعد الختم مباشرة يظهر إصدار الشهادة» أمراً واقعاً: لا ينتظر
    المديرُ أن يُخبره أحد، بل تُعرض عليه الأسماء المستحقّة.
    """
    _require_manager(current_user)
    query = await student_query(current_user, {**NOT_DELETED, "is_active": True})
    if query is None:
        return {"students": []}

    students = await db.students.find(query).to_list(2000)
    sids = [str(s["_id"]) for s in students]
    if not sids:
        return {"students": []}

    recs: dict = {sid: [] for sid in sids}
    async for r in db.recitations.find({**NOT_DELETED, "student_id": {"$in": sids}}):
        recs.setdefault(r["student_id"], []).append(r)

    issued: dict = {}
    async for c in db.certificates.find(
            {"student_id": {"$in": sids}, "kind": "milestone"},
            {"student_id": 1, "milestone": 1}):
        issued.setdefault(c["student_id"], set()).add(c.get("milestone"))

    out = []
    for s in students:
        sid = str(s["_id"])
        pages = compute_all(recs.get(sid, []), []).get("pages_memorized") or 0.0
        earned = [k for k, m in MILESTONES.items()
                  if pages >= int(m["juz"]) * PAGES_PER_JUZ - 0.5]
        pending = [k for k in earned if k not in issued.get(sid, set())]
        if pending:
            pending.sort(key=lambda k: int(MILESTONES[k]["order"]), reverse=True)
            out.append({
                "student_id": sid,
                "student_name": s.get("name"),
                "halaqah_name": s.get("halaqah_name"),
                "pages_memorized": round(pages, 1),
                "juz_memorized": round(pages / PAGES_PER_JUZ, 1),
                "pending": [{"milestone": k, "label": MILESTONES[k]["label"]} for k in pending],
            })

    out.sort(key=lambda r: -r["pages_memorized"])
    return {"students": out, "milestones": MILESTONES}


# ------------------------------------------------------------------ الإصدار
@router.post("/api/certificates/milestone")
async def issue_milestone(req: MilestoneCertificateCreate,
                          current_user: dict = Depends(get_current_user)):
    """شهادة حفظ: خمسة أجزاء، أو عشرة، أو نصف القرآن، أو الختم."""
    _require_manager(current_user)
    student = await check_student_access(req.student_id, current_user)

    milestone = MILESTONES.get(req.milestone)
    if not milestone:
        raise HTTPException(status_code=400, detail="محطّة غير معروفة")

    pages = await _pages_memorized(req.student_id)
    required = int(milestone["juz"]) * PAGES_PER_JUZ
    if pages < required - 0.5:
        raise HTTPException(
            status_code=409,
            detail=(f"لم يبلغ الطالب هذه المحطّة بعد: حفظ "
                    f"{round(pages / PAGES_PER_JUZ, 1)} جزءاً من {milestone['juz']}"))

    dup = await db.certificates.find_one(
        {"student_id": req.student_id, "kind": "milestone", "milestone": req.milestone})
    if dup:
        raise HTTPException(
            status_code=409,
            detail=f"أُصدرت هذه الشهادة مسبقاً برقم {dup.get('serial')}")

    center_id = student.get("center_id")
    doc = {
        "serial": await _next_serial(center_id or "system"),
        "kind": "milestone",
        "center_id": center_id,
        "center_name": await _center_name(center_id),
        "student_id": req.student_id,
        "student_name": student.get("name"),
        "halaqah_name": student.get("halaqah_name"),
        "title": "شهادة حفظ وتكريم",
        "subtitle": str(milestone["label"]),
        "milestone": req.milestone,
        "pages_memorized": round(pages, 1),
        "notes": req.notes,
        "issued_by": str(current_user["_id"]),
        "issued_by_name": current_user.get("name") or current_user.get("username"),
        "issued_at": utcnow(),
    }
    res = await db.certificates.insert_one(doc)
    await write_audit_log(
        actor_id=str(current_user["_id"]), center_id=center_id or "system",
        action="CERTIFICATE_ISSUED",
        payload={"serial": doc["serial"], "kind": "milestone",
                 "milestone": req.milestone, "student_id": req.student_id})
    return _shape({**doc, "_id": res.inserted_id})


@router.post("/api/certificates/competition/{contestant_id}")
async def issue_competition(contestant_id: str,
                            current_user: dict = Depends(get_current_user)):
    """
    شهادة مسابقة — بعد اعتماد المدير للنتائج.

    قبل الاعتماد الدرجةُ قابلة للتغيير، وشهادةٌ تحمل درجةً تتغيّر بعدها ورقةٌ
    لا تُصدَّق.
    """
    _require_manager(current_user)
    contestant = await db.competition_contestants.find_one(
        {"_id": safe_object_id(contestant_id)})
    if not contestant:
        raise HTTPException(status_code=404, detail="المتسابق غير موجود")

    comp = await db.competitions.find_one(
        {"_id": safe_object_id(contestant["competition_id"])})
    if not comp:
        raise HTTPException(status_code=404, detail="المسابقة غير موجودة")
    if current_user["role"] not in ("admin", "super_admin"):
        if comp.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="مسابقة تخصّ مركزاً آخر")

    if comp.get("status") not in ("approved", "archived"):
        raise HTTPException(
            status_code=409,
            detail="تُصدَر شهادة المسابقة بعد اعتماد النتائج — اعتمدها أوّلاً")
    if not (contestant.get("judge_scores") or []):
        raise HTTPException(status_code=409, detail="لم تُرصد درجاتُ هذا المتسابق")

    dup = await db.certificates.find_one({
        "kind": "competition",
        "competition_id": contestant["competition_id"],
        "student_id": contestant["student_id"]})
    if dup:
        raise HTTPException(
            status_code=409,
            detail=f"أُصدرت هذه الشهادة مسبقاً برقم {dup.get('serial')}")

    # الترتيب داخل الفرع يُحسب عند الإصدار ويُجمَّد على الورقة
    same_branch = await db.competition_contestants.find({
        "competition_id": contestant["competition_id"],
        "category": contestant.get("category")}).to_list(1000)
    same_branch.sort(key=lambda x: x.get("total_score") or 0, reverse=True)
    rank = next((i for i, x in enumerate(same_branch, 1)
                 if str(x["_id"]) == contestant_id), None)

    center_id = comp.get("center_id")
    doc = {
        "serial": await _next_serial(center_id or "system"),
        "kind": "competition",
        "center_id": center_id,
        "center_name": await _center_name(center_id),
        "student_id": contestant["student_id"],
        "student_name": contestant.get("student_name"),
        "halaqah_name": contestant.get("halaqah_name"),
        "title": "شهادة تقدير وتكريم",
        "subtitle": comp.get("title"),
        "competition_id": contestant["competition_id"],
        "branch": contestant.get("category"),
        "rank": rank,
        "score": contestant.get("total_score"),
        "judges_names": [j.get("teacher_name") for j in (comp.get("judges") or [])
                         if j.get("teacher_name")],
        "issued_by": str(current_user["_id"]),
        "issued_by_name": current_user.get("name") or current_user.get("username"),
        "issued_at": utcnow(),
    }
    res = await db.certificates.insert_one(doc)
    await write_audit_log(
        actor_id=str(current_user["_id"]), center_id=center_id or "system",
        action="CERTIFICATE_ISSUED",
        payload={"serial": doc["serial"], "kind": "competition",
                 "competition_id": contestant["competition_id"],
                 "student_id": contestant["student_id"]})
    return _shape({**doc, "_id": res.inserted_id})


@router.delete("/api/certificates/{certificate_id}")
async def revoke_certificate(certificate_id: str,
                             current_user: dict = Depends(get_current_user)):
    """
    إلغاء شهادةٍ أُصدرت خطأً — لاسمٍ خاطئ أو محطّةٍ خاطئة.

    الخطأ الإداري يقع، والنظام الذي لا يُصحَّح فيه يُجبر صاحبَه على الالتفاف
    عليه. والإلغاء يُسجَّل كما يُسجَّل الإصدار.
    """
    _require_manager(current_user)
    cert = await db.certificates.find_one({"_id": safe_object_id(certificate_id)})
    if not cert:
        raise HTTPException(status_code=404, detail="الشهادة غير موجودة")
    if current_user["role"] not in ("admin", "super_admin"):
        if cert.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="شهادة تخصّ مركزاً آخر")

    await db.certificates.delete_one({"_id": cert["_id"]})
    await write_audit_log(
        actor_id=str(current_user["_id"]), center_id=cert.get("center_id", "system"),
        action="CERTIFICATE_REVOKED",
        payload={"serial": cert.get("serial"), "student_id": cert.get("student_id")})
    return {"message": "أُلغيت الشهادة", "serial": cert.get("serial")}
