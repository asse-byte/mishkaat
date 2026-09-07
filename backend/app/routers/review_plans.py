"""خطط المراجعة."""

from app.clock import utcnow

from datetime import datetime
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from typing import Optional

from app.common import check_student_access, safe_object_id, serialize_doc
from app.db import db
from app.models import ReviewPlanCreate
from app.security import get_current_user

router = APIRouter()


# ==================== Review Plans (خطط المراجعة) ====================

@router.get("/api/review-plans")
async def get_review_plans(
    center_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على خطط المراجعة"""
    # [AUDIT-2026-05-22 fix: tight role gate + fail-closed; was leaking all plans to parents/students/scopeless managers]
    role = current_user["role"]
    if role not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {}
    if role == "center_manager":
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]
    elif role == "teacher":
        if not current_user.get("center_id"):
            return []
        teacher = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if not teacher:
            return []
        query["teacher_id"] = str(teacher["_id"])
    elif role == "admin" and center_id:
        query["center_id"] = center_id

    plans = await db.review_plans.find(query).sort("created_at", -1).to_list(500)
    result = []
    for p in plans:
        doc = serialize_doc(p)
        if doc.get("created_at") and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        result.append(doc)
    return result

@router.post("/api/review-plans")
async def create_review_plan(plan: ReviewPlanCreate, current_user: dict = Depends(get_current_user)):
    """إضافة خطة مراجعة"""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # [AUDIT-2026-05-22 fix: enforce center_id matches caller's center for non-admin;
    # validate student/teacher (if supplied) belong to the same center]
    if current_user["role"] != "admin":
        if plan.center_id != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بإنشاء خطة في مركز آخر")

    if plan.student_id:
        student = await check_student_access(plan.student_id, current_user)
        if student.get("center_id") != plan.center_id:
            raise HTTPException(status_code=400, detail="الطالب لا ينتمي للمركز المحدد")

    if plan.teacher_id and current_user["role"] != "admin":
        try:
            t_row = await db.teachers.find_one({"_id": safe_object_id(plan.teacher_id)})
        except HTTPException:
            t_row = None
        if not t_row or t_row.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="المعلم لا ينتمي لمركزك")

    data = plan.model_dump(exclude_none=True)
    data["created_at"] = utcnow()
    data["created_by"] = str(current_user["_id"])
    result = await db.review_plans.insert_one(data)
    data["id"] = str(result.inserted_id)
    data["created_at"] = data["created_at"].isoformat()
    return data


@router.put("/api/review-plans/{plan_id}")
async def update_review_plan(plan_id: str, patch: ReviewPlanCreate,
                             current_user: dict = Depends(get_current_user)):
    """تعديل خطّة مراجعة — لمن يملك إنشاءها."""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    plan = await db.review_plans.find_one({"_id": safe_object_id(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="الخطّة غير موجودة")
    if (current_user["role"] != "admin"
            and plan.get("center_id") != current_user.get("center_id")):
        raise HTTPException(status_code=403, detail="هذه الخطّة تخصّ مركزاً آخر")

    changes = {k: v for k, v in patch.model_dump(exclude_unset=True).items()
               if k not in ("center_id",)}
    changes["updated_at"] = utcnow()
    changes["updated_by"] = str(current_user["_id"])
    await db.review_plans.update_one({"_id": plan["_id"]}, {"$set": changes})
    return serialize_doc({**plan, **changes})


@router.delete("/api/review-plans/{plan_id}")
async def delete_review_plan(plan_id: str,
                             current_user: dict = Depends(get_current_user)):
    """حذف خطّة مراجعة."""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    plan = await db.review_plans.find_one({"_id": safe_object_id(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="الخطّة غير موجودة")
    if (current_user["role"] != "admin"
            and plan.get("center_id") != current_user.get("center_id")):
        raise HTTPException(status_code=403, detail="هذه الخطّة تخصّ مركزاً آخر")

    await db.review_plans.delete_one({"_id": plan["_id"]})
    return {"message": "حُذفت الخطّة"}
