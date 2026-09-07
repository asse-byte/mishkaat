"""
المسابقات القرآنية.

[إعادة بناء 2026-09-06 — قرار المالك]

    1. الفروع منفصلة تماماً. لكل فرعٍ ترتيبُه ونتائجُه وحده، فلا يُقارَن حافظُ
       جزء عمّ بحافظ القرآن كاملاً. والفروع قائمة مغلقة لا نصّ حرّ.

    2. لجنة التحكيم شيوخُ حلقات يُعيّنهم مديرُ المركز لهذه المسابقة. كلُّ محكّم
       يرصد درجتَه وحدها، والدرجة النهائية متوسّطُ درجات اللجنة — لا درجة واحدة
       يكتبها آخرُ من فتح الشاشة فوق درجة سابقه، كما كان.

    3. المسابقة تمرّ بحالات: active (تسجيل) ← grading (تحكيم) ← approved
       (اعتماد المدير) ← archived (أرشيف). و**المعتمَدة لا تُعدَّل**: لا تُرصَد
       درجة، ولا يُسجَّل متسابق، ولا يُغيَّر شيء. نتيجةٌ اعتُمدت وأُعلنت ثم
       تغيّرت تُفقد المسابقةَ معناها كلَّه.

    4. مسابقات السنوات الماضية تبقى ويُطَّلع عليها بالسنة.

الصلاحيات: إنشاءُ المسابقة وتعيينُ اللجنة والاعتمادُ للمدير. والرصدُ لأعضاء
اللجنة وحدهم — لا لكل شيخ. وشيخٌ ليس في اللجنة لا يرى المسابقة أصلاً.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.audit import write_audit_log
from app.clock import utcnow
from app.common import check_student_access, safe_object_id, serialize_doc
from app.db import db
from app.models import (
    COMPETITION_BRANCHES,
    CompetitionContestantCreate,
    CompetitionCreate,
    CompetitionUpdate,
    ContestantGrades,
)
from app.scope import teacher_record, visible_student_ids
from app.security import get_current_user

router = APIRouter()

MANAGERS = ("admin", "super_admin", "center_manager")
# الحالات التي لا يجوز فيها أيّ تعديل
FROZEN = ("approved", "archived")


# ------------------------------------------------------------------ مساعدات
async def _get_comp(comp_id: str, current_user: dict) -> dict:
    comp = await db.competitions.find_one({"_id": safe_object_id(comp_id)})
    if not comp:
        raise HTTPException(status_code=404, detail="المسابقة غير موجودة")
    if current_user["role"] not in ("admin", "super_admin"):
        if comp.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="مسابقة تخصّ مركزاً آخر")
    return comp


async def _judge_teacher_id(current_user: dict) -> Optional[str]:
    if current_user.get("role") != "teacher":
        return None
    t = await teacher_record(current_user)
    return str(t["_id"]) if t else None


def _is_judge(comp: dict, teacher_id: Optional[str]) -> bool:
    if not teacher_id:
        return False
    return any(j.get("teacher_id") == teacher_id for j in comp.get("judges", []))


async def _assert_can_grade(comp: dict, current_user: dict) -> Optional[dict]:
    """
    يُعيد سجلّ المحكّم إن كان المستخدم عضو لجنة. المدير لا يرصد.

    الرصدُ شهادةٌ على ما سمعه المحكّم، فهو لأعضاء اللجنة وحدهم — كما أن التسميع
    لشيخ الحلقة وحده. والمدير يعتمد النتيجة ولا يضعها.
    """
    if comp.get("status") in FROZEN:
        raise HTTPException(
            status_code=409,
            detail="المسابقة معتمَدة — لا تُعدَّل نتائجها")
    tid = await _judge_teacher_id(current_user)
    if not _is_judge(comp, tid):
        raise HTTPException(
            status_code=403,
            detail="رصد الدرجات لأعضاء لجنة التحكيم في هذه المسابقة وحدهم")
    t = await teacher_record(current_user)
    return t


def _recalc(contestant: dict) -> dict:
    """الدرجة النهائية = متوسّط درجات اللجنة."""
    scores = contestant.get("judge_scores") or []
    if not scores:
        return {"total_score": 0.0, "judges_count": 0, "grades": None}
    n = len(scores)
    avg = lambda k: round(sum(float(s.get(k) or 0) for s in scores) / n, 2)  # noqa: E731
    return {
        "total_score": round(sum(float(s.get("total") or 0) for s in scores) / n, 2),
        "judges_count": n,
        "grades": {
            "hifdh_score": avg("hifdh_score"),
            "tajweed_score": avg("tajweed_score"),
            "voice_score": avg("voice_score"),
        },
    }


def _branches_of(comp: dict) -> list:
    """فروعُ المسابقة. المسابقات المُنشأة قبل هذا البناء تحمل `categories`،
    فتُقرأ فروعُها منها — وإلا رُدّ تسجيلُ متسابقٍ في فرعٍ سُجّل فيه غيرُه."""
    return comp.get("branches") or comp.get("categories") or COMPETITION_BRANCHES


def _shape(doc: dict) -> dict:
    d = serialize_doc(doc)
    d.setdefault("status", "active")
    d["branches"] = _branches_of(d)
    d.setdefault("judges", [])
    # الواجهة القديمة تقرأ categories
    d["categories"] = d["branches"]
    if not d.get("year"):
        try:
            d["year"] = int(str(d.get("date", ""))[:4])
        except ValueError:
            d["year"] = utcnow().year
    if isinstance(d.get("created_at"), datetime):
        pass
    else:
        d["created_at"] = utcnow()
    return d


# ------------------------------------------------------------------ المسارات
@router.get("/api/competitions/branches")
async def list_branches(current_user: dict = Depends(get_current_user)):
    """الفروع المعتمدة — قائمة مغلقة تقرأها الواجهة ولا تكرّرها."""
    return {"branches": COMPETITION_BRANCHES}


@router.get("/api/competitions/my-role")
async def my_competition_role(current_user: dict = Depends(get_current_user)):
    """
    هل يظهر بند «المسابقات» لهذا المستخدم؟

    القائمة الجانبية لا تعرض المسابقات لشيخ الحلقة إلا إن كان عضو لجنة تحكيم في
    مسابقة **جارية**. وحين تنتهي المسابقة وتُعتمد يختفي البند عنه — فالتحكيم
    مهمّةٌ لها وقت، لا صلاحية دائمة.
    """
    role = current_user.get("role")
    if role in MANAGERS:
        return {"can_see": True, "is_judge": False, "teacher_id": None, "judging": []}
    if role == "student":
        return {"can_see": True, "is_judge": False, "teacher_id": None, "judging": []}
    if role != "teacher":
        return {"can_see": False, "is_judge": False, "teacher_id": None, "judging": []}

    tid = await _judge_teacher_id(current_user)
    if not tid:
        return {"can_see": False, "is_judge": False, "teacher_id": None, "judging": []}
    # «ما لم تُجمَّد» لا «active أو grading»: المسابقات المُنشأة قبل هذا البناء
    # لا تحمل حقل status أصلاً، و $in لا يطابق حقلاً غائباً — فكان المحكّم في
    # مسابقةٍ قديمة لا يرى بندَه ولا يعرف لماذا.
    rows = await db.competitions.find({
        "center_id": current_user.get("center_id"),
        "status": {"$nin": list(FROZEN)},
        "judges.teacher_id": tid,
    }).to_list(50)
    judging = [{"id": str(r["_id"]), "title": r.get("title")} for r in rows]
    return {"can_see": bool(judging), "is_judge": bool(judging),
            "teacher_id": tid, "judging": judging}


@router.post("/api/competitions")
async def create_competition(comp: CompetitionCreate,
                             current_user: dict = Depends(get_current_user)):
    """إنشاء مسابقة وتعيين لجنة تحكيمها — للإدارة."""
    if current_user["role"] not in MANAGERS:
        raise HTTPException(status_code=403, detail="إنشاء المسابقات من عمل إدارة المركز")
    center_id = current_user.get("center_id")
    if not center_id and current_user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=400, detail="لا يوجد مركز مرتبط بحسابك")

    bad = [b for b in (comp.branches or []) if b not in COMPETITION_BRANCHES]
    if bad:
        raise HTTPException(status_code=400, detail=f"فرع غير معتمد: {', '.join(bad)}")

    doc = comp.model_dump()
    doc["center_id"] = center_id
    doc["status"] = "active"
    doc["created_at"] = utcnow()
    doc["year"] = comp.year or int(str(comp.date)[:4] or utcnow().year)
    doc["branches"] = comp.branches or COMPETITION_BRANCHES

    # أسماء المحكّمين تُقرأ من السجلّ لا من الحمولة
    judges = []
    for j in comp.judges or []:
        t = await db.teachers.find_one({"_id": safe_object_id(j.teacher_id)})
        if not t or (center_id and t.get("center_id") != center_id):
            raise HTTPException(status_code=400, detail="محكّم لا ينتمي لمركزك")
        judges.append({"teacher_id": str(t["_id"]), "teacher_name": t.get("name")})
    doc["judges"] = judges

    res = await db.competitions.insert_one(doc)
    await write_audit_log(actor_id=str(current_user["_id"]), center_id=center_id or "system",
                          action="COMPETITION_CREATED",
                          payload={"title": doc["title"], "judges": len(judges)})
    return _shape({**doc, "_id": res.inserted_id})


@router.get("/api/competitions")
async def list_competitions(
    year: Optional[int] = None,
    include_archived: bool = Query(True),
    current_user: dict = Depends(get_current_user),
):
    """
    مسابقات المركز، أحدثها أوّلاً. `year` يفتح أرشيف سنةٍ بعينها.
    شيخُ الحلقة لا يرى إلا المسابقات التي هو في لجنتها.
    """
    role = current_user["role"]
    query: dict = {}
    if role not in ("admin", "super_admin"):
        cid = current_user.get("center_id")
        if not cid:
            return []
        query["center_id"] = cid
    if year:
        query["year"] = year
    if not include_archived:
        query["status"] = {"$ne": "archived"}

    if role == "teacher":
        tid = await _judge_teacher_id(current_user)
        if not tid:
            return []
        query["judges.teacher_id"] = tid

    rows = await db.competitions.find(query).sort([("year", -1), ("date", -1)]).to_list(200)
    return [_shape(r) for r in rows]


@router.get("/api/competitions/years")
async def competition_years(current_user: dict = Depends(get_current_user)):
    """السنوات التي فيها مسابقات — لفتح الأرشيف."""
    query: dict = {}
    if current_user["role"] not in ("admin", "super_admin"):
        cid = current_user.get("center_id")
        if not cid:
            return {"years": []}
        query["center_id"] = cid
    years = await db.competitions.distinct("year", query)
    return {"years": sorted([y for y in years if y], reverse=True)}


@router.put("/api/competitions/{comp_id}")
async def update_competition(comp_id: str, patch: CompetitionUpdate,
                             current_user: dict = Depends(get_current_user)):
    """تعديل المسابقة أو لجنتها — للإدارة، وما لم تُعتمد."""
    if current_user["role"] not in MANAGERS:
        raise HTTPException(status_code=403, detail="غير مصرح")
    comp = await _get_comp(comp_id, current_user)
    if comp.get("status") in FROZEN:
        raise HTTPException(status_code=409, detail="المسابقة معتمَدة — لا تُعدَّل")

    changes = {k: v for k, v in patch.model_dump(exclude_unset=True).items() if v is not None}
    if "branches" in changes:
        bad = [b for b in changes["branches"] if b not in COMPETITION_BRANCHES]
        if bad:
            raise HTTPException(status_code=400, detail=f"فرع غير معتمد: {', '.join(bad)}")
    if "judges" in changes:
        judges = []
        for j in changes["judges"]:
            t = await db.teachers.find_one({"_id": safe_object_id(j["teacher_id"])})
            if not t:
                raise HTTPException(status_code=400, detail="محكّم غير موجود")
            # كفحص الإنشاء: لا يُعيَّن محكّمٌ من مركزٍ آخر
            if (current_user["role"] not in ("admin", "super_admin")
                    and t.get("center_id") != current_user.get("center_id")):
                raise HTTPException(status_code=400, detail="محكّم لا ينتمي لمركزك")
            judges.append({"teacher_id": str(t["_id"]), "teacher_name": t.get("name")})
        changes["judges"] = judges
    if not changes:
        return _shape(comp)
    await db.competitions.update_one({"_id": comp["_id"]}, {"$set": changes})
    return _shape({**comp, **changes})


@router.post("/api/competitions/{comp_id}/approve")
async def approve_competition(comp_id: str, current_user: dict = Depends(get_current_user)):
    """
    اعتماد نتائج المسابقة — للإدارة.

    بعده تُجمَّد: لا رصدَ ولا تسجيلَ ولا تعديل. النتيجة المُعلنة التي تتغيّر
    بعد إعلانها تُفقد المسابقةَ معناها.
    """
    if current_user["role"] not in MANAGERS:
        raise HTTPException(status_code=403, detail="اعتماد النتائج من عمل إدارة المركز")
    comp = await _get_comp(comp_id, current_user)
    if comp.get("status") in FROZEN:
        return {"message": "المسابقة معتمَدة مسبقاً", "status": comp.get("status")}

    ungraded = await db.competition_contestants.count_documents(
        {"competition_id": comp_id, "judge_scores": {"$in": [None, []]}})
    await db.competitions.update_one({"_id": comp["_id"]}, {"$set": {
        "status": "approved", "approved_at": utcnow(),
        "approved_by": current_user.get("username"),
    }})
    await write_audit_log(actor_id=str(current_user["_id"]),
                          center_id=comp.get("center_id", "system"),
                          action="COMPETITION_APPROVED",
                          payload={"title": comp.get("title"), "ungraded": ungraded})
    return {"message": "اعتُمدت النتائج وجُمّدت", "status": "approved",
            "ungraded_contestants": ungraded}


@router.post("/api/competitions/{comp_id}/archive")
async def archive_competition(comp_id: str, current_user: dict = Depends(get_current_user)):
    """نقل مسابقة معتمَدة إلى الأرشيف."""
    if current_user["role"] not in MANAGERS:
        raise HTTPException(status_code=403, detail="غير مصرح")
    comp = await _get_comp(comp_id, current_user)
    if comp.get("status") != "approved":
        raise HTTPException(status_code=409, detail="تُؤرشَف المسابقة بعد اعتمادها فقط")
    await db.competitions.update_one({"_id": comp["_id"]}, {"$set": {"status": "archived"}})
    return {"message": "أُرشِفت المسابقة", "status": "archived"}


@router.post("/api/competitions/{comp_id}/register")
async def register_contestant(comp_id: str, contestant: CompetitionContestantCreate,
                              current_user: dict = Depends(get_current_user)):
    """تسجيل طالب في فرع. المدير لأيّ طالب، والمحكّمُ لطلاب حلقته."""
    role = current_user["role"]
    if role not in MANAGERS + ("teacher",):
        raise HTTPException(status_code=403, detail="غير مصرح")
    comp = await _get_comp(comp_id, current_user)
    if comp.get("status") in FROZEN:
        raise HTTPException(status_code=409, detail="المسابقة معتمَدة — لا يُسجَّل فيها")

    if role == "teacher":
        tid = await _judge_teacher_id(current_user)
        if not _is_judge(comp, tid):
            raise HTTPException(status_code=403,
                                detail="التسجيل لأعضاء لجنة التحكيم أو الإدارة")

    branches = _branches_of(comp)
    if contestant.category not in branches:
        raise HTTPException(status_code=400,
                            detail=f"الفرع غير موجود في هذه المسابقة: {contestant.category}")

    student = await check_student_access(contestant.student_id, current_user)

    dup = await db.competition_contestants.find_one(
        {"competition_id": comp_id, "student_id": contestant.student_id})
    if dup:
        raise HTTPException(status_code=400, detail="الطالب مسجَّل في هذه المسابقة")

    doc = contestant.model_dump()
    doc.update({
        "competition_id": comp_id, "center_id": comp.get("center_id"),
        "student_name": student.get("name"), "halaqah_name": student.get("halaqah_name"),
        "judge_scores": [], "total_score": 0.0, "judges_count": 0,
        "grades": None, "created_at": utcnow(),
    })
    res = await db.competition_contestants.insert_one(doc)
    return serialize_doc({**doc, "_id": res.inserted_id})


@router.get("/api/competitions/{comp_id}/contestants")
async def get_contestants(comp_id: str, branch: Optional[str] = None,
                          current_user: dict = Depends(get_current_user)):
    """
    المتسابقون مرتَّبون **داخل كل فرع على حدة**.

    الترتيب العام بلا فصل الفروع يضع حافظ جزء عمّ في ذيل قائمةٍ صدرُها حفظةُ
    القرآن كاملاً، وهي مقارنة لا معنى لها. فتُعاد النتائج مجموعةً بالفرع، ولكلٍّ
    ترتيبُه من واحد.
    """
    comp = await _get_comp(comp_id, current_user)
    role = current_user["role"]

    if role == "teacher":
        tid = await _judge_teacher_id(current_user)
        if not _is_judge(comp, tid):
            raise HTTPException(status_code=403, detail="لست في لجنة تحكيم هذه المسابقة")

    query: dict = {"competition_id": comp_id}
    if branch:
        query["category"] = branch

    # [قرار المالك 2026-09-07] «الطالب يرى كلَّ شيء في المسابقات القرآنية:
    # ترتيبَه وترتيبَ الآخرين وجميعَ الفروع الأخرى — ولا يمكنه إصدار الشهادة.»
    #
    # وكان يُرشَّح إلى صفّه هو وحده. والأسوأ أن الترتيب يُحسب بعد الترشيح، فيخرج
    # «رتبتُه 1» في كل فرعٍ يظهر فيه — رقمٌ خاطئ لا نطاقٌ مضيَّق. والمسابقة
    # حدثٌ مُعلَن: نتائجُها تُقرأ على المنبر ويعرفها الحاضرون كلُّهم.
    #
    # وهذا **قرارٌ يخالف** ما استقرّ عليه سابقاً في نطاق الطالب (بياناته وحده)،
    # ومحصورٌ في المسابقات: أسماءُ المتسابقين ودرجاتُهم فقط، لا ملفّاتُهم.

    rows = await db.competition_contestants.find(query).to_list(1000)

    # متسابقون سُجّلوا قبل هذا البناء لا يحملون اسم الطالب ولا حلقته، فيظهر
    # صفٌّ بلا اسم. يُقرأ الاسم من سجلّ الطالب عند العرض — ولا يُكتب على السجلّ
    # القديم: قراءةٌ لا هجرةَ بيانات.
    missing = [r["student_id"] for r in rows
               if r.get("student_id") and not r.get("student_name")]
    lookup: dict = {}
    if missing:
        async for st in db.students.find(
                {"_id": {"$in": [safe_object_id(m) for m in missing]}}):
            lookup[str(st["_id"])] = st

    grouped: dict = {}
    for r in rows:
        doc = serialize_doc(r)
        doc.setdefault("judge_scores", [])
        doc["judges_count"] = doc.get("judges_count") or len(doc["judge_scores"])
        doc["total_score"] = doc.get("total_score") or 0.0
        st = lookup.get(doc.get("student_id"))
        if st:
            doc["student_name"] = doc.get("student_name") or st.get("name")
            doc["halaqah_name"] = doc.get("halaqah_name") or st.get("halaqah_name")
        grouped.setdefault(doc.get("category") or "غير محدَّد", []).append(doc)

    out = []
    for b in _branches_of(comp):
        entries = sorted(grouped.pop(b, []), key=lambda x: x.get("total_score") or 0, reverse=True)
        for i, e in enumerate(entries, 1):
            e["rank_in_branch"] = i
        out.append({"branch": b, "contestants": entries, "count": len(entries)})
    # فروع قديمة لم تعد في القائمة المعتمدة — تُعرض ولا تُخفى
    for b, entries in grouped.items():
        entries.sort(key=lambda x: x.get("total_score") or 0, reverse=True)
        for i, e in enumerate(entries, 1):
            e["rank_in_branch"] = i
        out.append({"branch": b, "contestants": entries, "count": len(entries), "legacy": True})

    return {"competition": _shape(comp), "branches": out}


@router.post("/api/competitions/contestants/{contestant_id}/grade")
async def grade_contestant(contestant_id: str, grades: ContestantGrades,
                           current_user: dict = Depends(get_current_user)):
    """
    رصد درجة محكّمٍ واحد.

    كل محكّم يرصد درجتَه وحدها، والنهائيةُ متوسّطُ اللجنة. وكان الرصد يكتب درجةً
    واحدة على المتسابق: فآخرُ محكّمٍ يفتح الشاشة يمحو رصدَ من قبله بلا أثر، ولا
    يُعرف من أعطى ماذا. كلُّ رصدٍ الآن باسم صاحبه ووقتِه.
    """
    contestant = await db.competition_contestants.find_one(
        {"_id": safe_object_id(contestant_id)})
    if not contestant:
        raise HTTPException(status_code=404, detail="المتسابق غير موجود")
    comp = await _get_comp(contestant["competition_id"], current_user)

    if current_user["role"] in MANAGERS:
        raise HTTPException(
            status_code=403,
            detail="رصد الدرجات للجنة التحكيم — الإدارة تعتمد النتيجة ولا تضعها")
    judge = await _assert_can_grade(comp, current_user)

    for field, limit in (("hifdh_score", 70), ("tajweed_score", 20), ("voice_score", 10)):
        v = getattr(grades, field)
        if v < 0 or v > limit:
            raise HTTPException(status_code=400,
                                detail=f"{field} يجب أن تكون بين 0 و {limit}")

    entry = {
        "judge_teacher_id": str(judge["_id"]),
        "judge_name": judge.get("name"),
        "hifdh_score": grades.hifdh_score,
        "tajweed_score": grades.tajweed_score,
        "voice_score": grades.voice_score,
        "total": round(grades.hifdh_score + grades.tajweed_score + grades.voice_score, 2),
        "graded_at": utcnow(),
    }
    scores = [s for s in (contestant.get("judge_scores") or [])
              if s.get("judge_teacher_id") != entry["judge_teacher_id"]]
    scores.append(entry)

    updated = {**contestant, "judge_scores": scores}
    calc = _recalc(updated)
    await db.competition_contestants.update_one(
        {"_id": contestant["_id"]}, {"$set": {"judge_scores": scores, **calc}})
    if comp.get("status") == "active":
        await db.competitions.update_one({"_id": comp["_id"]}, {"$set": {"status": "grading"}})

    return serialize_doc({**updated, **calc, "_id": contestant["_id"]})


@router.delete("/api/competitions/contestants/{contestant_id}")
async def withdraw_contestant(contestant_id: str,
                              current_user: dict = Depends(get_current_user)):
    """
    سحبُ متسابقٍ سُجّل خطأً — في فرعٍ ليس فرعَه، أو انسحب.

    ولم يكن ثمّة سبيل: المتسابق يُسجَّل ولا يُرفع إلا بحذف المسابقة كلِّها.
    ولا يُسحَب بعد اعتماد النتائج — الترتيب المُعلَن لا يتغيّر تحت أقدام من
    نُشر ترتيبُهم معه.
    """
    if current_user["role"] not in MANAGERS:
        raise HTTPException(status_code=403, detail="سحبُ المتسابقين من عمل الإدارة")

    contestant = await db.competition_contestants.find_one(
        {"_id": safe_object_id(contestant_id)})
    if not contestant:
        raise HTTPException(status_code=404, detail="المتسابق غير موجود")

    comp = await _get_comp(contestant["competition_id"], current_user)
    if comp.get("status") in FROZEN:
        raise HTTPException(
            status_code=409, detail="المسابقة معتمَدة — لا يُسحَب منها متسابق")

    await db.competition_contestants.delete_one({"_id": contestant["_id"]})
    return {"message": "سُحب المتسابق", "student_name": contestant.get("student_name")}


@router.delete("/api/competitions/{comp_id}")
async def delete_competition(comp_id: str, current_user: dict = Depends(get_current_user)):
    """حذف مسابقة لم تُعتمد. المعتمَدة تُؤرشَف ولا تُحذف."""
    if current_user["role"] not in MANAGERS:
        raise HTTPException(status_code=403, detail="غير مصرح")
    comp = await _get_comp(comp_id, current_user)
    if comp.get("status") in FROZEN:
        raise HTTPException(status_code=409,
                            detail="المسابقة معتمَدة — تُؤرشَف ولا تُحذف")
    await db.competition_contestants.delete_many({"competition_id": comp_id})
    await db.competitions.delete_one({"_id": comp["_id"]})
    return {"message": "حُذفت المسابقة"}
