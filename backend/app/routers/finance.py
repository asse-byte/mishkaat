"""الرسوم والرواتب والمصروفات."""

from app.clock import utcnow

from datetime import datetime
from fastapi import APIRouter, Request
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from typing import Optional

from app.audit import write_audit_log
from app.common import check_student_access, parse_date_boundary, safe_object_id, scoped_student_ids, serialize_doc, NOT_VOIDED, client_ip
from app.db import db
from app.models import ExpenseCreate, FeeCreate, FeeStatus, SalaryCreate
from app.security import get_current_user

router = APIRouter()


# ==================== Fees Routes ====================

@router.get("/api/fees")
async def get_fees(
    status_filter: Optional[FeeStatus] = Query(None, alias="status"),
    student_id: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=5000),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    الحصول على سجلات الرسوم.

    [AUDIT-2026-09-03 fix: الواجهة تطلب /fees?status=pending منذ البداية، والخادم لا يعرف
     المعامل أصلاً فيتجاهله FastAPI بصمت ويعيد كل الرسوم — فتظهر «الرسوم المعلّقة» في
     التقارير وقد أُضيف إليها كل رسم مدفوع. المعامل صار مُعرَّفاً ومُتحقَّقاً منه.]
    """
    # [AUDIT-2026-05-22 fix: enforce role-based scoping; admin sees all, others restricted to own data]
    role = current_user["role"]
    # [إصلاح 2026-09-06] المحفّظ كان يقرأ رسوم المركز كلَّه — مبالغَ كل طالب
    # وحالةَ سدادها. المال شأن الإدارة، ولا صلة له بعمل شيخ الحلقة.
    if role not in ["admin", "center_manager", "parent", "student"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # الرسوم الملغاة لا تُعرض ولا يُطالَب بها
    query: dict = dict(NOT_VOIDED)

    if role in ("center_manager", "teacher"):
        if not current_user.get("center_id"):
            return []
        students = await db.students.find(
            {"center_id": current_user["center_id"], "is_active": True}, {"_id": 1}
        ).to_list(5000)
        student_ids = [str(s["_id"]) for s in students]
        if not student_ids:
            return []
        query["student_id"] = {"$in": student_ids}
    elif role == "parent":
        phone = current_user.get("phone")
        if not phone:
            return []
        children = await db.students.find({"parent_phone": phone}, {"_id": 1}).to_list(100)
        student_ids = [str(s["_id"]) for s in children]
        if not student_ids:
            return []
        query["student_id"] = {"$in": student_ids}
    elif role == "student":
        s_doc = await db.students.find_one({"user_id": str(current_user["_id"])})
        if not s_doc and current_user.get("phone"):
            s_doc = await db.students.find_one({"phone": current_user["phone"]})
        if not s_doc:
            return []
        query["student_id"] = str(s_doc["_id"])
    # admin: no extra filter

    if status_filter:
        query["status"] = status_filter

    if student_id:
        # الفلترة تُضيَّق داخل النطاق المسموح ولا تتجاوزه أبداً
        allowed = query.get("student_id")
        if isinstance(allowed, dict) and student_id not in allowed.get("$in", []):
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لرسوم هذا الطالب")
        if isinstance(allowed, str) and allowed != student_id:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لرسوم هذا الطالب")
        if allowed is None and role != "admin":
            raise HTTPException(status_code=403, detail="غير مصرح")
        query["student_id"] = student_id

    fees = await db.fees.find(query).skip(skip).limit(limit).to_list(limit)
    result = []
    for f in fees:
        doc = serialize_doc(f)
        if doc.get("paid_date") and isinstance(doc["paid_date"], datetime):
            doc["paid_date"] = doc["paid_date"].isoformat()
        result.append(doc)
    return result

@router.post("/api/fees")
async def create_fee(fee: FeeCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء رسوم جديدة"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: secure BOLA center isolation]
    student = await check_student_access(fee.student_id, current_user)

    if fee.amount is None or fee.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    if not parse_date_boundary(fee.due_date):
        raise HTTPException(status_code=400, detail="تاريخ الاستحقاق غير صالح (YYYY-MM-DD)")

    # رسمٌ مكرّر لنفس الطالب ونفس النوع في شهر الاستحقاق نفسه — الرسمُ الشهري
    # يقع مرّةً في الشهر، وتكرارُه يُطالب وليَّ الأمر بالمبلغ مرّتين.
    month = (fee.due_date or "")[:7]
    if month:
        dup = await db.fees.find_one({
            "student_id": fee.student_id,
            "fee_type": fee.fee_type,
            "due_date": {"$regex": f"^{month}"},
            **NOT_VOIDED,
        })
        if dup:
            raise HTTPException(
                status_code=409,
                detail=(f"على هذا الطالب رسمٌ من النوع نفسه في {month} "
                        f"بمبلغ {dup.get('amount')} — عدّله بدل إضافة رسمٍ ثانٍ"))

    fee_dict = fee.model_dump()
    fee_dict["status"] = "pending"
    fee_dict["paid_date"] = None
    # [AUDIT-2026-09-03 fix: الرسوم لم تكن تحمل center_id ولا تاريخ إنشاء — فلا يمكن حصر
    #  رسوم مركز ولا حساب إيراد فترة زمنية. يُكتبان الآن من مستند الطالب ووقت الإنشاء.]
    fee_dict["center_id"] = student.get("center_id")
    fee_dict["created_at"] = utcnow()
    fee_dict["created_by"] = str(current_user["_id"])
    if not fee_dict.get("student_name"):
        fee_dict["student_name"] = student.get("name")
    result = await db.fees.insert_one(fee_dict)

    return {
        "id": str(result.inserted_id),
        "student_id": fee_dict["student_id"],
        "student_name": fee_dict.get("student_name"),
        "amount": fee_dict["amount"],
        "due_date": fee_dict["due_date"],
        "fee_type": fee_dict["fee_type"],
        "notes": fee_dict.get("notes"),
        "status": fee_dict["status"],
        "paid_date": fee_dict["paid_date"]
    }

@router.post("/api/fees/{fee_id}/pay")
async def pay_fee(fee_id: str, current_user: dict = Depends(get_current_user)):
    """تسجيل دفع رسوم"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    fee_obj_id = safe_object_id(fee_id)
    fee = await db.fees.find_one({"_id": fee_obj_id})
    if not fee:
        raise HTTPException(status_code=404, detail="الرسوم غير موجودة")
        
    # Verify BOLA access to this student's fees
    await check_student_access(fee["student_id"], current_user)

    # [AUDIT-2026-09-03 fix: كان دفع رسم مدفوع مسبقاً يعيد كتابة تاريخ الدفع ويضيف قيد
    #  تحصيل ثانياً في سجل التدقيق — نقرتان على الزر تعنيان تحصيلين في السجل المالي.]
    if fee.get("status") == "paid":
        raise HTTPException(status_code=409, detail="هذه الرسوم مدفوعة مسبقاً")

    paid_at = utcnow()
    updated_res = await db.fees.update_one(
        {"_id": fee_obj_id, "status": {"$ne": "paid"}},
        {"$set": {
            "status": "paid",
            "paid_date": paid_at,
            "collected_by": str(current_user["_id"]),
        }}
    )
    if updated_res.modified_count == 0:
        raise HTTPException(status_code=409, detail="هذه الرسوم مدفوعة مسبقاً")

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="collect_fee",
        payload={"fee_id": fee_id, "amount": fee["amount"], "student_id": fee["student_id"]}
    )
    
    updated = await db.fees.find_one({"_id": fee_obj_id})
    doc = serialize_doc(updated)
    if doc.get("paid_date") and isinstance(doc["paid_date"], datetime):
        doc["paid_date"] = doc["paid_date"].isoformat()
    return doc

# ==================== تصحيح الأعمال المالية ====================
#
# [قرار المالك 2026-09-07] «أيّ أعمال إدارية يقوم بها مدير المركز اجعله قابلاً
# للتعديل بعد قيامه به، لأن أيّ عملٍ إداري ممكن يصير فيه خطأ. إذاً من الأفضل
# إضافة ميزة التعديل أو أحياناً الحذف.»
#
# ولم يكن للرسوم ولا للرواتب سبيلٌ إلى التصحيح: لا PUT ولا DELETE. مبلغٌ كُتب
# خطأً يبقى في مجموع المركز إلى الأبد، ورسمٌ سُجّل لطالبٍ غيرِ صاحبه يُطالَب به.
# والنظام الذي لا يُصحَّح فيه الخطأ يُجبر صاحبَه على الالتفاف عليه.


@router.put("/api/fees/{fee_id}")
async def update_fee(fee_id: str, fee: FeeCreate,
                     current_user: dict = Depends(get_current_user)):
    """تصحيح رسمٍ: مبلغه أو تاريخه أو نوعه أو ملاحظته."""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    existing = await db.fees.find_one({"_id": safe_object_id(fee_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="الرسم غير موجود")
    await check_student_access(existing.get("student_id"), current_user)

    if fee.amount is None or fee.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    if not parse_date_boundary(fee.due_date):
        raise HTTPException(status_code=400, detail="تاريخ الاستحقاق غير صالح (YYYY-MM-DD)")

    changes = {
        "amount": fee.amount,
        "due_date": fee.due_date,
        "fee_type": fee.fee_type,
        "notes": fee.notes,
        "updated_at": utcnow(),
        "updated_by": str(current_user["_id"]),
    }
    await db.fees.update_one({"_id": existing["_id"]}, {"$set": changes})
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=existing.get("center_id") or current_user.get("center_id", "system"),
        action="update_fee",
        payload={"fee_id": fee_id, "from": existing.get("amount"), "to": fee.amount})
    return serialize_doc({**existing, **changes})


@router.delete("/api/fees/{fee_id}")
async def void_fee(fee_id: str, reason: str = Query(..., min_length=3),
                   current_user: dict = Depends(get_current_user)):
    """
    إلغاء رسمٍ سُجّل خطأً — بسببٍ مكتوب.

    إلغاءٌ لا حذف: الرسم المدفوع يقابله مالٌ قُبض، وحذفُ سطره من القاعدة يُخفي
    المال ولا يُعيده. فيُوسَم voided فيسقط من المطالبات والمجاميع، ويبقى في
    السجلّ بسببه ومَن ألغاه.
    """
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    existing = await db.fees.find_one({"_id": safe_object_id(fee_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="الرسم غير موجود")
    await check_student_access(existing.get("student_id"), current_user)
    if existing.get("voided"):
        raise HTTPException(status_code=409, detail="هذا الرسم ملغىً مسبقاً")

    await db.fees.update_one({"_id": existing["_id"]}, {"$set": {
        "voided": True, "void_reason": reason,
        "voided_at": utcnow(), "voided_by": str(current_user["_id"])}})
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=existing.get("center_id") or current_user.get("center_id", "system"),
        action="void_fee",
        payload={"fee_id": fee_id, "amount": existing.get("amount"), "reason": reason})
    return {"message": "أُلغي الرسم"}


@router.put("/api/salaries/{salary_id}")
async def update_salary(salary_id: str, salary: SalaryCreate,
                        current_user: dict = Depends(get_current_user)):
    """تصحيح راتبٍ مصروف: مبلغه أو شهره أو ملاحظته."""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    existing = await db.salaries.find_one({"_id": safe_object_id(salary_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="سجلّ الراتب غير موجود")
    if (current_user["role"] == "center_manager"
            and existing.get("center_id") != current_user.get("center_id")):
        raise HTTPException(status_code=403, detail="هذا السجلّ يخصّ مركزاً آخر")
    if salary.amount is None or salary.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    # نقلُ الراتب إلى شهرٍ فيه راتبٌ لهذا المعلّم يُنتج ازدواجاً من الباب الخلفي
    if salary.month != existing.get("month"):
        clash = await db.salaries.find_one({
            "_id": {"$ne": existing["_id"]},
            "teacher_id": existing.get("teacher_id"),
            "month": salary.month,
            "center_id": existing.get("center_id"),
            **NOT_VOIDED})
        if clash:
            raise HTTPException(
                status_code=409,
                detail=f"لهذا المعلّم راتبٌ مصروف في {salary.month} بالفعل")

    changes = {
        "amount": salary.amount,
        "month": salary.month,
        "notes": salary.notes,
        "updated_at": utcnow(),
        "updated_by": str(current_user["_id"]),
    }
    await db.salaries.update_one({"_id": existing["_id"]}, {"$set": changes})
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=existing.get("center_id", "system"),
        action="update_salary",
        payload={"salary_id": salary_id, "from": existing.get("amount"),
                 "to": salary.amount, "month": salary.month})
    return serialize_doc({**existing, **changes})


@router.delete("/api/salaries/{salary_id}")
async def void_salary(salary_id: str, reason: str = Query(..., min_length=3),
                      current_user: dict = Depends(get_current_user)):
    """إلغاء صرفِ راتبٍ سُجّل خطأً — بسببٍ مكتوب، ويبقى في السجلّ."""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    existing = await db.salaries.find_one({"_id": safe_object_id(salary_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="سجلّ الراتب غير موجود")
    if (current_user["role"] == "center_manager"
            and existing.get("center_id") != current_user.get("center_id")):
        raise HTTPException(status_code=403, detail="هذا السجلّ يخصّ مركزاً آخر")
    if existing.get("voided"):
        raise HTTPException(status_code=409, detail="هذا السجلّ ملغىً مسبقاً")

    await db.salaries.update_one({"_id": existing["_id"]}, {"$set": {
        "voided": True, "void_reason": reason,
        "voided_at": utcnow(), "voided_by": str(current_user["_id"])}})
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=existing.get("center_id", "system"),
        action="void_salary",
        payload={"salary_id": salary_id, "amount": existing.get("amount"),
                 "reason": reason})
    return {"message": "أُلغي سجلّ الراتب"}


@router.put("/api/expenses/{expense_id}")
async def update_expense(expense_id: str, expense: ExpenseCreate,
                         current_user: dict = Depends(get_current_user)):
    """تصحيح مصروف. (الإلغاء كان موجوداً، والتعديل لم يكن.)"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    existing = await db.expenses.find_one({"_id": safe_object_id(expense_id)})
    if not existing:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
    if (current_user["role"] == "center_manager"
            and existing.get("center_id") != current_user.get("center_id")):
        raise HTTPException(status_code=403, detail="هذا المصروف يخصّ مركزاً آخر")
    if existing.get("voided"):
        raise HTTPException(status_code=409, detail="لا يُعدَّل مصروفٌ ملغى")
    if expense.amount is None or expense.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")

    changes = {
        "title": expense.title,
        "amount": expense.amount,
        "category": expense.category,
        "notes": expense.notes,
        "updated_at": utcnow(),
        "updated_by": str(current_user["_id"]),
    }
    await db.expenses.update_one({"_id": existing["_id"]}, {"$set": changes})
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=existing.get("center_id", "system"),
        action="update_expense",
        payload={"expense_id": expense_id, "from": existing.get("amount"),
                 "to": expense.amount})
    return serialize_doc({**existing, **changes})


@router.get("/api/fees/student/{student_id}")
async def get_student_fees(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على رسوم طالب"""
    await check_student_access(student_id, current_user)
    fees = await db.fees.find({"student_id": student_id}).to_list(100)
    result = []
    for f in fees:
        doc = serialize_doc(f)
        if doc.get("paid_date") and isinstance(doc["paid_date"], datetime):
            doc["paid_date"] = doc["paid_date"].isoformat()
        result.append(doc)
    return result

# ==================== Salaries Routes ====================

@router.get("/api/salaries")
async def get_salaries(current_user: dict = Depends(get_current_user)):
    """الحصول على سجلات الرواتب"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    # [AUDIT-2026-05-22 fix: fail-closed for managers without center_id (was leaking all centers)]
    query = {}
    if current_user["role"] == "center_manager":
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]
    salaries = await db.salaries.find(
        {**query, **NOT_VOIDED}).sort("created_at", -1).to_list(200)
    result = []
    for s in salaries:
        doc = serialize_doc(s)
        if doc.get("created_at") and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        result.append(doc)
    return result

@router.post("/api/salaries")
async def create_salary(salary: SalaryCreate, current_user: dict = Depends(get_current_user)):
    """إضافة راتب معلم"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # [AUDIT-2026-05-22 fix: center_manager may only pay salaries inside their own center,
    # and the teacher being paid must belong to that center as well]
    if current_user["role"] == "center_manager":
        if salary.center_id != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة راتب لمركز آخر")
        teacher_obj_id = safe_object_id(salary.teacher_id)
        teacher_row = await db.teachers.find_one({"_id": teacher_obj_id})
        if not teacher_row:
            raise HTTPException(status_code=404, detail="المعلم غير موجود")
        if teacher_row.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="هذا المعلم لا ينتمي لمركزك")

    # [قرار المالك 2026-09-07] «ليس من الجيد أن يسمح النظام للمستخدم بإجراء
    # بعض العمليات مرّتين، التي تقع في الشهر مرّة واحدة — مثل دفع الراتب
    # الشهري لمعلّمٍ واحد مرّتين في شهرٍ واحد.»
    #
    # وكان الراتب يُقبل بلا حدّ: كلُّ ضغطةٍ تكتب سجلّاً جديداً، وتُضاف إلى
    # مصروفات المركز، وتكتب سطر تدقيقٍ ثانياً — ولا شيء يقول إنّ الرجل قُبض له
    # هذا الشهر. والخطأُ هنا مالٌ يخرج مرّتين.
    dup = await db.salaries.find_one({
        "teacher_id": salary.teacher_id,
        "month": salary.month,
        "center_id": salary.center_id,
        **NOT_VOIDED,
    })
    if dup:
        raise HTTPException(
            status_code=409,
            detail=(f"صُرف راتب هذا المعلّم لشهر {salary.month} مسبقاً "
                    f"بمبلغ {dup.get('amount')} — عدّل السجلّ القائم أو احذفه"))

    salary_dict = salary.model_dump()
    salary_dict["created_at"] = utcnow()
    salary_dict["status"] = "paid"
    result = await db.salaries.insert_one(salary_dict)
    
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=salary.center_id,
        action="pay_salary",
        payload={"teacher_id": salary.teacher_id, "amount": salary.amount, "month": salary.month}
    )
    
    # [إصلاح 2026-09-04] insert_one يحقن _id في القاموس المُمرَّر إليه نفسه، فكانت
    # النسخة تحمل ObjectId لا يعرف FastAPI ترميزه — وإضافة الراتب كان يفشل بـ500 دائماً.
    # نُسقِط _id صراحةً بدل الاتّكال على أن القاموس لم يُمَسّ.
    doc = {k: v for k, v in salary_dict.items() if k != "_id"}
    doc["id"] = str(result.inserted_id)
    doc["created_at"] = doc["created_at"].isoformat()
    return doc

# ==================== Expenses Routes ====================

@router.get("/api/expenses")
async def get_expenses(current_user: dict = Depends(get_current_user)):
    """الحصول على المصروفات"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    # [AUDIT-2026-05-22 fix: fail-closed for managers without center_id (was leaking all centers)]
    query = {}
    if current_user["role"] == "center_manager":
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]
    expenses = await db.expenses.find({**query, **NOT_VOIDED}).sort("created_at", -1).to_list(200)
    result = []
    for e in expenses:
        doc = serialize_doc(e)
        if doc.get("created_at") and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        result.append(doc)
    return result

@router.post("/api/expenses")
async def create_expense(expense: ExpenseCreate, current_user: dict = Depends(get_current_user)):
    """إضافة مصروف"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: secure BOLA center-level isolation]
    if current_user["role"] != "admin" and expense.center_id != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة مصروف لمركز آخر")
        
    exp_dict = expense.model_dump()
    exp_dict["created_at"] = utcnow()
    result = await db.expenses.insert_one(exp_dict)
    
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=expense.center_id,
        action="create_expense",
        payload={"title": expense.title, "amount": expense.amount, "category": expense.category}
    )
    
    # [إصلاح 2026-09-04] insert_one يحقن _id في القاموس المُمرَّر إليه نفسه، فكانت
    # النسخة تحمل ObjectId لا يعرف FastAPI ترميزه — وإضافة المصروف كان يفشل بـ500 دائماً.
    # نُسقِط _id صراحةً بدل الاتّكال على أن القاموس لم يُمَسّ.
    doc = {k: v for k, v in exp_dict.items() if k != "_id"}
    doc["id"] = str(result.inserted_id)
    doc["created_at"] = doc["created_at"].isoformat()
    return doc

@router.delete("/api/expenses/{expense_id}")
async def delete_expense(
    expense_id: str,
    request: Request,
    reason: Optional[str] = Query(None, max_length=300, description="سبب الإبطال"),
    current_user: dict = Depends(get_current_user),
):
    """إبطال مصروف (لا يُمحى — يبقى في السجل ويخرج من المجاميع)"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    exp_obj_id = safe_object_id(expense_id)
    expense = await db.expenses.find_one({"_id": exp_obj_id})
    if not expense:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
        
    if current_user["role"] != "admin" and expense.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف مصروف لمركز آخر")

    if expense.get("voided"):
        raise HTTPException(status_code=409, detail="هذا المصروف مُبطَل مسبقاً")

    # [إصلاح 2026-09-04] كان delete_one يمحو الصفّ فعلياً.
    # المصروف قيدٌ ماليّ يدخل صافي الربح: محوُه يغيّر أرقام فترة ماضية بلا أثر
    # يُراجَع، ويخالف مبدأ المشروع في أن السجل المالي يُصحَّح ولا يُمحى. صار
    # إبطالاً موثَّقاً: الصفّ يبقى، ويخرج من كل مجموع، ويُسجَّل من أبطله ومتى ولماذا.
    await db.expenses.update_one(
        {"_id": exp_obj_id},
        {"$set": {
            "voided": True,
            "voided_at": utcnow(),
            "voided_by": str(current_user["_id"]),
            "void_reason": (reason or "").strip() or None,
        }},
    )

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=expense.get("center_id", "system"),
        action="delete_expense",
        payload={"expense_id": expense_id, "title": expense.get("title"),
                 "amount": expense.get("amount"), "reason": (reason or "").strip() or None},
        client_ip=client_ip(request),
    )

    return {"message": "تم إبطال المصروف", "voided": True}

# ==================== Financial Summary (إضافة 2026-09-03) ====================

async def _sum_amounts(collection, match: dict) -> float:
    """
    مجموع حقل amount عبر تجميع قاعدة البيانات.

    [AUDIT-2026-09-03 perf: كانت /api/super/dashboard/stats تسحب كل الرسوم وكل الرواتب وكل
     المصروفات إلى ذاكرة الخادم وتجمعها في حلقة Python — يكبر ببطء مع كل مركز جديد إلى أن
     تتجاوز الصفحة المهلة. الجمع الآن داخل قاعدة البيانات.]
    """
    pipeline = [{"$match": match}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
    async for row in collection.aggregate(pipeline):
        return float(row.get("total") or 0.0)
    return 0.0

@router.get("/api/finance/summary")
async def get_finance_summary(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    center_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    [AUDIT-2026-09-03 addition] الملخّص المالي للمركز خلال فترة: المُحصَّل، المعلّق،
    الرواتب، المصروفات، والصافي.

    كانت صفحة المالية في الواجهة تجمع هذه الأرقام بنفسها من قوائم مُقسَّمة إلى صفحات
    (page 1 فقط)، فتظهر أرقام لا تعبّر عن الفترة كاملة. الحساب صار في الخادم على كل السجلات.
    """
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    if role == "center_manager":
        scope_center = current_user.get("center_id")
        if not scope_center:
            raise HTTPException(status_code=400, detail="حسابك غير مرتبط بمركز")
        if center_id and center_id != scope_center:
            raise HTTPException(status_code=403, detail="غير مصرح لك بعرض مالية مركز آخر")
    else:
        scope_center = center_id  # None = كل المراكز للمدير العام

    start = parse_date_boundary(from_date, end=False)
    end = parse_date_boundary(to_date, end=True)
    if from_date and not start:
        raise HTTPException(status_code=400, detail="تاريخ البداية غير صالح (YYYY-MM-DD)")
    if to_date and not end:
        raise HTTPException(status_code=400, detail="تاريخ النهاية غير صالح (YYYY-MM-DD)")
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="تاريخ البداية بعد تاريخ النهاية")

    def window(field: str) -> dict:
        rng = {}
        if start:
            rng["$gte"] = start
        if end:
            rng["$lte"] = end
        return {field: rng} if rng else {}

    # الرسوم: قد لا تحمل السجلات القديمة center_id، فيُستكمل النطاق بمعرّفات طلاب المركز
    fee_scope: dict = {}
    if scope_center:
        ids = await scoped_student_ids(scope_center)
        fee_scope = {"$or": [{"center_id": scope_center}, {"student_id": {"$in": ids}}]}

    # الملغى يسقط من كل مجموع. الوسمُ وحده بلا استبعادٍ من الحساب يعني إلغاءً
    # في الشاشة ومالاً باقياً في الأرقام — وهو أسوأ من ألّا يكون الإلغاء أصلاً.
    collected = await _sum_amounts(
        db.fees, {**fee_scope, "status": "paid", **window("paid_date"), **NOT_VOIDED})
    pending = await _sum_amounts(
        db.fees, {**fee_scope, "status": {"$ne": "paid"}, **NOT_VOIDED})
    pending_count = await db.fees.count_documents(
        {**fee_scope, "status": {"$ne": "paid"}, **NOT_VOIDED})

    center_scope = {"center_id": scope_center} if scope_center else {}
    salaries = await _sum_amounts(
        db.salaries, {**center_scope, **window("created_at"), **NOT_VOIDED})
    expenses = await _sum_amounts(db.expenses, {**center_scope, **window("created_at"), **NOT_VOIDED})

    return {
        "center_id": scope_center,
        "from": start.isoformat() if start else None,
        "to": end.isoformat() if end else None,
        "revenue": {"fees_collected": round(collected, 2)},
        "outstanding": {"fees_pending": round(pending, 2), "fees_pending_count": pending_count},
        "costs": {
            "salaries_paid": round(salaries, 2),
            "expenses": round(expenses, 2),
            "total": round(salaries + expenses, 2),
        },
        "net_balance": round(collected - salaries - expenses, 2),
        "currency": "FCFA",
        "note": "المُحصَّل يُحسب بتاريخ الدفع الفعلي، والتكاليف بتاريخ التسجيل",
    }
