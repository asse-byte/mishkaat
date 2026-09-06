"""التسميع."""

from app.clock import utcnow

from datetime import datetime
from datetime import timedelta
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from typing import Optional

from app.audit import write_audit_log
from app.common import NOT_DELETED, check_student_access, client_ip, safe_object_id, serialize_doc
from app.config import XP_PER_PAGE, logger
from app.db import db
from app.gamification import award_xp, evaluate_badges
from app.metrics import compute_all, pages_of
from app.models import RecitationCreate
from app.routers.performance import invalidate_model
from app.scope import teacher_only
from app.security import get_current_user

router = APIRouter()


# ==================== Recitations Routes ====================

@router.get("/api/recitations")
async def get_recitations(
    center_id: Optional[str] = None,
    halaqah_id: Optional[str] = None,
    student_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """الحصول على قائمة التسميعات - مفلترة حسب الدور"""
    # [AUDIT-2026-05-22 fix: tight role gate + center isolation; closed dead-code BOLA for students/parents]
    role = current_user["role"]
    if role not in ["admin", "center_manager", "teacher", "student", "parent", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {}
    allowed_student_ids: Optional[set] = None  # whitelist for non-admin scopes

    user_cid = current_user.get("center_id")
    if role not in ["super_admin", "admin"]:
        if not user_cid:
            return []

    # SaaS Multi-tenant Isolation
    if role in ["super_admin", "admin"]:
        if center_id:
            students = await db.students.find(
                {"center_id": center_id, "is_active": True}, {"_id": 1}
            ).to_list(2000)
            allowed_student_ids = {str(s["_id"]) for s in students}
    elif role == "center_manager":
        students = await db.students.find(
            {"center_id": user_cid, "is_active": True}, {"_id": 1}
        ).to_list(5000)
        allowed_student_ids = {str(s["_id"]) for s in students}
    elif role == "teacher":
        # [AUDIT-2026-05-22 fix: deny-by-default if no teacher row found]
        teacher = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if not teacher:
            return []
        query["teacher_id"] = str(teacher["_id"])
    elif role == "student":
        # [AUDIT-2026-05-22 fix: replace dead `if False` branch with real ownership lookup]
        student_doc = await db.students.find_one({"user_id": str(current_user["_id"])})
        if not student_doc and current_user.get("phone"):
            student_doc = await db.students.find_one({"phone": current_user["phone"]})
        if not student_doc:
            return []
        allowed_student_ids = {str(student_doc["_id"])}
    elif role == "parent":
        phone = current_user.get("phone")
        if not phone:
            return []
        children = await db.students.find({"parent_phone": phone}, {"_id": 1}).to_list(100)
        allowed_student_ids = {str(s["_id"]) for s in children}
        if not allowed_student_ids:
            return []

    # [AUDIT-2026-05-22 fix: query-param student_id MUST stay within caller's whitelist]
    if student_id:
        if allowed_student_ids is not None and student_id not in allowed_student_ids:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لتسميعات هذا الطالب")
        query["student_id"] = student_id
    elif allowed_student_ids is not None:
        query["student_id"] = {"$in": list(allowed_student_ids)}

    if halaqah_id:
        # [AUDIT-2026-05-22 fix: verify halaqah belongs to caller's center before filtering by it]
        if role in ("center_manager", "teacher") and current_user.get("center_id"):
            try:
                h = await db.halaqat.find_one({"_id": safe_object_id(halaqah_id)})
            except HTTPException:
                h = None
            if not h or h.get("center_id") != current_user.get("center_id"):
                raise HTTPException(status_code=403, detail="حلقة لا تنتمي لمركزك")
        query["halaqah_id"] = halaqah_id

    recitations = await db.recitations.find({**query, **NOT_DELETED}).sort("date", -1).to_list(limit)
    result = []
    for r in recitations:
        doc = serialize_doc(r)
        doc["date"] = doc.get("date", utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result

async def _award_session_rewards(recitation_dict: dict, recitation_id: str, student: dict) -> None:
    """
    نقاط الخبرة والأوسمة بعد تسميعة واحدة (FR12، FR13).

    النقاط بعدد الصفحات لا بعدد الجلسات: عشرُ صفحات في جلسة تساوي عشراً في
    عشر جلسات، فلا يُكافأ تفتيتُ الجلسة. والمفتاح الفريد على (الطالب، السبب،
    المصدر) يجعل إعادةَ المعالجة بلا أثر.
    """
    center_id = student.get("center_id")
    student_id = recitation_dict["student_id"]

    pages = pages_of(recitation_dict)
    await award_xp(student_id, round(pages * XP_PER_PAGE), "recitation", recitation_id, center_id)

    recitations = await db.recitations.find(
        {**NOT_DELETED, "student_id": student_id}).to_list(5000)
    attendance = await db.attendance.find({"student_id": student_id}).to_list(5000)
    await evaluate_badges(student_id, compute_all(recitations, attendance), center_id)

    # تاريخ المركز تغيّر، فنموذج التنبؤ المخزَّن لم يعد على أحدث البيانات
    invalidate_model(center_id)


@router.post("/api/recitations")
async def create_recitation(recitation: RecitationCreate, current_user: dict = Depends(get_current_user)):
    """تسجيل تسميع جديد"""
    # [قرار المالك 2026-09-06] التسميع شهادةٌ على ما سمعه الشيخ بأذنه. مديرُ
    # المركز يقرأ السجلّ كلَّه ويُصحّحه بالتعديل والحذف، ولا يُنشئ سجلّاً يشهد
    # فيه على مجلسٍ لم يحضره.
    teacher_only(current_user, "تسجيل التسميع")

    # [AUDIT-2026-05-22 fix: enforce student belongs to caller's center before logging recitation]
    # ومنذ 2026-09-06 تفرض هذه البوّابة أن يكون الطالب من حلقة هذا الشيخ نفسه.
    student = await check_student_access(recitation.student_id, current_user)

    # [AUDIT-2026-05-22 fix: a teacher may only record recitations under their own teacher identity]
    if current_user["role"] == "teacher":
        teacher_row = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if not teacher_row or recitation.teacher_id != str(teacher_row["_id"]):
            raise HTTPException(status_code=403, detail="لا يمكن تسجيل تسميع باسم معلم آخر")

    recitation_dict = recitation.model_dump()
    recitation_dict["date"] = utcnow()
    result = await db.recitations.insert_one(recitation_dict)
    recitation_id = str(result.inserted_id)

    # [إضافة 2026-09-05 — FR12/FR13 في تقرير Halaqtna]
    # حفظُ الجلسة يُطلق ثلاثة أفعال تلقائية (UC15-UC17 في التقرير): إعادة حساب
    # المقاييس، وتحديث التنبؤ، ومنح النقاط. الأوّلان يُحسبان عند القراءة هنا
    # (لا تُخزَّن قيمة مشتقّة، انظر app/metrics.py)، والثالث يُكتب الآن.
    #
    # الفشل هنا لا يُسقط تسجيل التسميع: التسميعة هي السجلّ الحقيقي، والنقاط
    # طبقةُ تحفيز فوقه. ولو رُبط مصيرهما لفقد المحفّظُ عملَه لخلل في التحفيز.
    try:
        await _award_session_rewards(recitation_dict, recitation_id, student)
    except Exception as exc:  # pragma: no cover - لا يُفشل المسار الأساسي
        logger.warning(f"gamification after recitation {recitation_id} failed: {exc}")

    return {
        "id": recitation_id,
        "student_id": recitation_dict["student_id"],
        "student_name": recitation_dict.get("student_name"),
        "teacher_id": recitation_dict["teacher_id"],
        "teacher_name": recitation_dict.get("teacher_name"),
        "surah_number": recitation_dict.get("surah_number"),
        "surah_name": recitation_dict["surah_name"],
        "start_ayah": recitation_dict["start_ayah"],
        "end_ayah": recitation_dict["end_ayah"],
        "evaluation": recitation_dict["evaluation"],
        "mistakes_count": recitation_dict["mistakes_count"],
        "hesitations_count": recitation_dict.get("hesitations_count", 0),
        "tajweed_errors_count": recitation_dict.get("tajweed_errors_count", 0),
        "notes": recitation_dict.get("notes"),
        "recitation_type": recitation_dict["recitation_type"],
        "date": recitation_dict["date"].isoformat()
    }

@router.get("/api/recitations/student/{student_id}")
async def get_student_recitations(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على تسميعات طالب محدد"""
    await check_student_access(student_id, current_user)
    recitations = await db.recitations.find({**NOT_DELETED, "student_id": student_id}).sort("date", -1).to_list(100)
    result = []
    for r in recitations:
        doc = serialize_doc(r)
        doc["date"] = doc.get("date", utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result

@router.delete("/api/recitations/{recitation_id}")
async def delete_recitation(
    recitation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    حذف تسميع (حذف ناعم).

    [إصلاح 2026-09-03] صفحة التسميع فيها زر «حذف» منذ البداية يستدعي
    PUT /api/recitations/{id} — وهي نقطة لا وجود لها في الخادم. الاستجابة 404 كانت تُبتلع في
    catch صامت، فيؤكّد المعلّم الحذف ولا يحدث شيء ويبقى التسميع في الدرجات.

    الحذف ناعم لا نهائي: التسميع يقرّر جزءاً من تقييم الطالب، فإبقاؤه في قاعدة البيانات يسمح
    بمراجعة ما جرى. ويُستبعَد بعدها من كل حساب (القائمة، سجل الشرف، الترتيب، التحليلات، التنبؤ).
    """
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    rec_obj_id = safe_object_id(recitation_id)
    rec = await db.recitations.find_one({"_id": rec_obj_id})
    if not rec:
        raise HTTPException(status_code=404, detail="التسميع غير موجود")
    if rec.get("is_deleted"):
        raise HTTPException(status_code=409, detail="هذا التسميع محذوف مسبقاً")

    # الطالب يحدّد المركز — وهو الفحص نفسه الذي يحرس بقية مسارات التسميع
    await check_student_access(rec.get("student_id"), current_user)

    # المعلّم لا يحذف إلا تسميعاً سجّله بنفسه؛ حذف عمل زميله من صلاحية الإدارة
    if current_user["role"] == "teacher":
        teacher_row = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if not teacher_row or rec.get("teacher_id") != str(teacher_row["_id"]):
            raise HTTPException(status_code=403, detail="لا يمكنك حذف تسميع سجّله معلم آخر")

    await db.recitations.update_one(
        {"_id": rec_obj_id},
        {"$set": {
            "is_deleted": True,
            "deleted_at": utcnow(),
            "deleted_by": str(current_user["_id"]),
        }},
    )

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="DELETE_RECITATION",
        payload={
            "recitation_id": recitation_id,
            "student_id": rec.get("student_id"),
            "surah_name": rec.get("surah_name"),
            "evaluation": rec.get("evaluation"),
        },
        client_ip=client_ip(request),
    )
    return {"message": "تم حذف التسميع بنجاح"}

@router.get("/api/analytics/predict/{student_id}")
async def predict_completion(student_id: str, current_user: dict = Depends(get_current_user)):
    """حساب مؤشر الإتقان والتنبؤ بموعد ختم القرآن أو الجزء الحالي"""
    student = await check_student_access(student_id, current_user)
    
    recitations = await db.recitations.find({**NOT_DELETED, "student_id": student_id}).sort("date", 1).to_list(2000)
    
    TOTAL_QURAN_VERSES = 6236
    
    mastery_scores = []
    total_new_verses = 0
    new_recitations = []
    
    for r in recitations:
        mistakes = r.get("mistakes_count", 0)
        hesitations = r.get("hesitations_count", 0)
        tajweed_errors = r.get("tajweed_errors_count", 0)
        
        score = max(0.0, 100.0 - (mistakes * 4.0 + hesitations * 1.5 + tajweed_errors * 2.0))
        mastery_scores.append(score)
        
        if r.get("recitation_type") == "new":
            new_recitations.append(r)
            verses_count = max(1, r.get("end_ayah", 0) - r.get("start_ayah", 0) + 1)
            total_new_verses += verses_count
            
    avg_mastery = sum(mastery_scores) / len(mastery_scores) if mastery_scores else 85.0
    
    now = utcnow()
    thirty_days_ago = now - timedelta(days=30)
    recent_verses = 0
    for r in new_recitations:
        r_date = r.get("date", now)
        if isinstance(r_date, str):
            try:
                r_date = datetime.fromisoformat(r_date)
            except ValueError:
                r_date = now
        if r_date >= thirty_days_ago:
            verses_count = max(1, r.get("end_ayah", 0) - r.get("start_ayah", 0) + 1)
            recent_verses += verses_count
            
    momentum = recent_verses / (30.0 / 7.0)
    
    expected_completion_date = None
    confidence = 70
    
    if len(new_recitations) >= 2:
        first_date = new_recitations[0].get("date", now)
        if isinstance(first_date, str):
            try:
                first_date = datetime.fromisoformat(first_date)
            except ValueError:
                first_date = now
                
        x = []
        y = []
        accumulated = 0
        for r in new_recitations:
            r_date = r.get("date", now)
            if isinstance(r_date, str):
                try:
                    r_date = datetime.fromisoformat(r_date)
                except ValueError:
                    r_date = now
            days = (r_date - first_date).days
            verses_count = max(1, r.get("end_ayah", 0) - r.get("start_ayah", 0) + 1)
            accumulated += verses_count
            x.append(float(days))
            y.append(float(accumulated))
            
        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        num = 0.0
        den = 0.0
        for xi, yi in zip(x, y):
            num += (xi - mean_x) * (yi - mean_y)
            den += (xi - mean_x) ** 2
            
        if den > 0:
            slope = num / den
            intercept = mean_y - slope * mean_x
            
            y_pred = [slope * xi + intercept for xi in x]
            ss_tot = sum((yi - mean_y) ** 2 for yi in y)
            ss_res = sum((yi - ypi) ** 2 for yi, ypi in zip(y, y_pred))
            r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0
            
            confidence = max(50, min(82, int(r_squared * 82)))
            
            remaining_verses = max(0, TOTAL_QURAN_VERSES - accumulated)
            if slope > 0.05:
                days_to_complete = remaining_verses / slope
                expected_date = now + timedelta(days=days_to_complete)
                expected_completion_date = expected_date.strftime("%Y-%m-%d")
            else:
                daily_rate = max(0.1, accumulated / max(1, x[-1]))
                days_to_complete = remaining_verses / daily_rate
                expected_date = now + timedelta(days=days_to_complete)
                expected_completion_date = expected_date.strftime("%Y-%m-%d")
                confidence = max(50, int(confidence * 0.8))
        else:
            slope = 0
    else:
        remaining_verses = TOTAL_QURAN_VERSES - total_new_verses
        daily_rate = 5.0
        days_to_complete = remaining_verses / daily_rate
        expected_date = now + timedelta(days=days_to_complete)
        expected_completion_date = expected_date.strftime("%Y-%m-%d")
        confidence = 60
        
    return {
        "student_id": student_id,
        "student_name": student.get("name"),
        "average_mastery_score": round(avg_mastery, 1),
        "momentum_verses_per_week": round(momentum, 1),
        "total_verses_memorized": total_new_verses,
        "remaining_verses": max(0, TOTAL_QURAN_VERSES - total_new_verses),
        "predicted_completion_date": expected_completion_date,
        "confidence_percentage": confidence,
        "accuracy_bracket": "82% consistent linear projection" if confidence >= 75 else "consistent daily rate fallback"
    }
