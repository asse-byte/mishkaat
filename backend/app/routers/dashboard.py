"""لوحة التحكم والتحليلات."""

from app.clock import utcnow

from datetime import datetime
from datetime import timedelta
from fastapi import APIRouter
from fastapi import Depends

from app.common import NOT_DELETED, check_student_access, scoped_student_ids, serialize_doc
from app.db import db
from app.pii import decrypt_student_doc
from app.scoring import compute_student_scores
from app.scope import student_query, visible_halaqah_ids, visible_student_ids
from app.security import get_current_user

router = APIRouter()


@router.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """
    الحصول على إحصائيات لوحة التحكم.

    [AUDIT-2026-09-03 fix — رقمان خاطئان دائماً على الصفحة الرئيسية]
    كان نطاق المركز يُطبَّق على مجموعتَي attendance و fees عبر حقل center_id، وهما لا يحتويان
    هذا الحقل أصلاً (سجل الحضور فيه student_id و halaqah_id فقط، والرسوم فيها student_id فقط).
    فكانت النتيجة صفراً حتمياً: «نسبة الحضور 0%» و«الرسوم المعلّقة 0» لكل مدير مركز ومعلم،
    مهما بلغ عدد السجلات. النطاق الآن عبر طلاب المركز، والحقل يُكتب من الآن فصاعداً على
    السجلات الجديدة (انظر POST /api/attendance و POST /api/fees) فتصير الاستعلامات أسرع لاحقاً.
    كذلك كان التعليق يقول «آخر 30 يوماً» بينما الحساب يشمل كل التاريخ، فلا تتحرك النسبة أبداً.
    """
    role = current_user["role"]
    center_id = current_user.get("center_id")

    query_filter = {}
    if role != "super_admin" and center_id:
        query_filter["center_id"] = center_id

    # [إصلاح 2026-09-06] العدّاد كان على المركز كلّه، فتقول لوحةُ شيخ الحلقة إن
    # عنده أربعين طالباً وحلقتُه فيها ستّة. الرقم الذي لا يخصّه لا يفيده، ويُخبره
    # بحجم ما لا يراه.
    scoped_students_q = await student_query(current_user, {"is_active": True})
    total_students = (
        0 if scoped_students_q is None
        else await db.students.count_documents(scoped_students_q)
    )
    scoped_halaqah_ids = await visible_halaqah_ids(current_user)
    if scoped_halaqah_ids is None:
        total_teachers = await db.teachers.count_documents({**query_filter, "is_active": True})
        total_halaqat_scoped = None
    else:
        # المحفّظ يَعُدّ نفسه واحداً، وحلقاته وحدها
        total_teachers = 1 if role == "teacher" else 0
        total_halaqat_scoped = len(scoped_halaqah_ids)

    # Non-super admins only count their own center
    if role == "super_admin":
        total_centers = await db.centers.count_documents({"is_active": True})
    else:
        total_centers = 1 if center_id else 0

    total_halaqat = (
        await db.halaqat.count_documents({**query_filter, "is_active": True})
        if total_halaqat_scoped is None else total_halaqat_scoped
    )

    # نطاق السجلات المرتبطة بالطلاب (حضور/رسوم)
    student_scope: dict = {}
    if role != "super_admin" and center_id:
        # سجلّات الحضور والرسوم تُحصر بمعرّفات طلاب النطاق نفسه لا بالمركز
        ids = await visible_student_ids(current_user)
        if ids is None:
            ids = await scoped_student_ids(center_id)
        if not ids:
            return {
                "total_students": total_students,
                "total_teachers": total_teachers,
                "total_centers": total_centers,
                "total_halaqat": total_halaqat,
                "attendance_rate": 0.0,
                "pending_fees": 0,
            }
        student_scope = {"student_id": {"$in": ids}}

    pending_fees = await db.fees.count_documents({**student_scope, "status": "pending"})

    # نسبة الحضور خلال آخر 30 يوماً فعلاً
    since = utcnow() - timedelta(days=30)
    window = {**student_scope, "date": {"$gte": since}}
    total_attendance = await db.attendance.count_documents(window)
    present_attendance = await db.attendance.count_documents({**window, "status": {"$in": ["present", "late"]}})
    attendance_rate = 0.0
    if total_attendance > 0:
        attendance_rate = round((present_attendance / total_attendance) * 100, 1)

    return {
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_centers": total_centers,
        "total_halaqat": total_halaqat,
        "attendance_rate": attendance_rate,
        "pending_fees": pending_fees,
    }

@router.get("/api/dashboard/honor-roll")
async def get_honor_roll(current_user: dict = Depends(get_current_user)):
    """حساب التقييم الذكي وسجل الشرف (المعادلة الذكية)"""

    # [إصلاح 2026-09-06] كان الترتيب على طلاب المركز كلّه، فيرى شيخُ الحلقة
    # أسماءَ طلابٍ ليسوا من حلقته ودرجاتِهم. سجلّ الشرف يُحفّز داخل الحلقة،
    # ومقارنةُ طالبٍ بمن لا يُدرّسه شيخُه ليست من شأنه.
    query_filter = await student_query(current_user, {"is_active": True})
    if query_filter is None:
        return []

    students = await db.students.find(query_filter).to_list(2000)
    scored = await compute_student_scores(students, days=30)
    return [{k: v for k, v in s.items() if k != "has_data"} for s in scored[:5]]

@router.get("/api/analytics/rankings")
async def get_analytics_rankings(current_user: dict = Depends(get_current_user)):
    """الحصول على الترتيب لجميع الطلاب (أفضل الطلاب والطلاب الضعفاء)"""

    query_filter = await student_query(current_user, {"is_active": True})
    if query_filter is None:
        return []

    students = await db.students.find(query_filter).to_list(2000)
    enrollment_by_id = {
        str(s["_id"]): (s.get("enrollment_date").isoformat() if isinstance(s.get("enrollment_date"), datetime) else None)
        for s in students
    }

    scored = await compute_student_scores(students, days=90)  # ثلاثة أشهر للترتيب
    rankings = []
    for s in scored:
        score = s["score"]
        rankings.append({
            **{k: v for k, v in s.items() if k != "has_data"},
            "category": "best" if score >= 85 else "weak" if score < 65 else "average",
            "enrollment_date": enrollment_by_id.get(s["id"]),
        })
    return rankings

@router.get("/api/analytics/student/{student_id}")
async def get_student_analytics(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على الأداء التاريخي للطالب المعين"""
    student = await check_student_access(student_id, current_user)
        
    six_months_ago = utcnow() - timedelta(days=180)
    
    recitations = await db.recitations.find({
        **NOT_DELETED,
        "student_id": student_id,
        "date": {"$gte": six_months_ago}
    }).sort("date", 1).to_list(500)
    
    attendances = await db.attendance.find({
        "student_id": student_id,
        "date": {"$gte": six_months_ago}
    }).sort("date", 1).to_list(500)
    
    eval_map = {"excellent": 100, "good": 80, "acceptable": 60, "needs_improvement": 40}
    att_map = {"present": 100, "late": 80, "excused": 60, "absent": 0}
    
    timeline = {}
    
    for r in recitations:
        d = r["date"].strftime("%Y-%m-%d") if isinstance(r["date"], datetime) else str(r["date"])[:10]
        if d not in timeline:
            timeline[d] = {"date": d, "recitation_score": None, "attendance_score": None, "mistakes": 0}
        
        score = eval_map.get(r.get("evaluation", "good"), 80)
        if timeline[d]["recitation_score"] is None:
            timeline[d]["recitation_score"] = score
        else:
            timeline[d]["recitation_score"] = (timeline[d]["recitation_score"] + score) / 2
        timeline[d]["mistakes"] += r.get("mistakes_count", 0)
        
    for a in attendances:
        d = a.get("date")
        if isinstance(d, datetime):
            d = d.strftime("%Y-%m-%d")
        elif isinstance(d, str):
            d = d[:10]
        else:
            continue
            
        if d not in timeline:
            timeline[d] = {"date": d, "recitation_score": None, "attendance_score": None, "mistakes": 0}
        
        timeline[d]["attendance_score"] = att_map.get(a.get("status", "present"), 100)
        
    timeline_list = [v for k, v in sorted(timeline.items())]
    
    return {
        # [AUDIT-2026-05-22 fix: decrypt PII before serialization]
        "student": serialize_doc(decrypt_student_doc(student)),
        "timeline": timeline_list
    }
