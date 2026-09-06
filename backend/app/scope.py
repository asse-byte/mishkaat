"""
نطاق كل دور — مصدر واحد لحدوده.

المشكلة التي أنشأت هذه الوحدة: كان النظام يحصر بالمركز ولا يعرف الحلقة أصلاً،
فشيخُ الحلقة يقرأ كل طلاب المركز — أسماءهم، وهواتف أوليائهم، وتسميعاتهم،
وحضورهم، ومقاييس أدائهم، وتاريخ ختمهم المتوقَّع، والرسوم المالية — ويستطيع
تسجيل تسميع لطالب ليس من حلقته. سبعة عشر تسريباً، كلُّها من أصلٍ واحد.

فلو رُقّع كلُّ موضع على حدة لعاد التسريب مع أوّل نقطة نهاية جديدة. الحدود هنا
في مكان واحد، وكل نقطة نهاية تسأل عنها.

    القاعدة:
      admin / super_admin   بلا حصر (إدارة النظام)
      center_manager        مركزُه كاملاً — يقرأ كل شيء فيه
      teacher               حلقاتُه التي يُدرّسها وطلابُها، لا غير
      student / parent      الطالبُ نفسه، واسمُ حلقته وشيخِها فقط

الرابط: users → teachers.user_id → halaqat.teacher_id → students.halaqah_id
"""

from typing import List, Optional, Set

from fastapi import HTTPException, status

from app.common import NOT_DELETED
from app.db import db

# الأدوار التي ترى نظامها كلَّه
GLOBAL_ROLES = {"admin", "super_admin"}
# الأدوار المحصورة في مركز واحد
CENTER_ROLES = {"center_manager"}
# الأدوار المحصورة في حلقة
HALAQAH_ROLES = {"teacher"}
# الأدوار المحصورة في طالب واحد
SELF_ROLES = {"student", "parent"}


async def teacher_record(current_user: dict) -> Optional[dict]:
    """وثيقة المحفّظ المرتبطة بحساب المستخدم."""
    return await db.teachers.find_one(
        {"user_id": str(current_user["_id"]), "is_active": True}
    )


async def teacher_halaqah_ids(current_user: dict) -> List[str]:
    """
    معرّفات الحلقات التي يُدرّسها هذا المحفّظ.

    قائمة فارغة تعني «لا حلقة له» — وهي ليست خطأً: محفّظ سُجّل ولم يُسنَد إليه
    شيء بعد. النتيجة أن نطاقه فارغ، فلا يرى طلاباً أصلاً. هذا هو السلوك الصحيح:
    الافتراض عند غياب الإسناد هو المنع لا السماح.
    """
    teacher = await teacher_record(current_user)
    if not teacher:
        return []
    rows = await db.halaqat.find(
        {"teacher_id": str(teacher["_id"]), "is_active": True}, {"_id": 1}
    ).to_list(200)
    return [str(r["_id"]) for r in rows]


async def own_student_ids(current_user: dict) -> List[str]:
    """
    الطلاب الذين يخصّون حساب طالب أو وليّ أمر.

    بنفس قواعد check_student_access: الطالب بمعرّف حسابه أو رقم هاتفه، ووليّ
    الأمر برقم هاتفه. **لا بالاسم** — الاسم قابل للتعديل ذاتياً من الملف
    الشخصي، فمطابقتُه تعني أن إعادة التسمية باسم زميل تفتح ملفَّه.
    """
    role = current_user.get("role")
    uid, phone = str(current_user["_id"]), current_user.get("phone")
    ors: List[dict] = []
    if role == "student":
        ors.append({"user_id": uid})
        if phone:
            ors.append({"phone": phone})
    elif role == "parent":
        if phone:
            ors += [{"parent_phone": phone}, {"phone": phone}]
    if not ors:
        return []
    rows = await db.students.find({"$or": ors}, {"_id": 1}).to_list(50)
    return [str(r["_id"]) for r in rows]


async def visible_halaqah_ids(current_user: dict) -> Optional[List[str]]:
    """
    الحلقات التي يراها هذا المستخدم. None تعني «بلا حصر بالحلقة».

    المحفّظ: حلقاتُه. الطالب ووليّ الأمر: حلقة الطالب وحدها.
    """
    role = current_user.get("role")
    if role in GLOBAL_ROLES or role in CENTER_ROLES:
        return None
    if role in HALAQAH_ROLES:
        return await teacher_halaqah_ids(current_user)
    if role in SELF_ROLES:
        sids = await own_student_ids(current_user)
        if not sids:
            return []
        from bson import ObjectId
        rows = await db.students.find(
            {"_id": {"$in": [ObjectId(s) for s in sids]}}, {"halaqah_id": 1}
        ).to_list(50)
        return [r["halaqah_id"] for r in rows if r.get("halaqah_id")]
    return []


async def visible_student_ids(current_user: dict) -> Optional[List[str]]:
    """
    معرّفات الطلاب داخل نطاق المستخدم. None تعني «بلا حصر بقائمة».

    تُستعمل حين يكون الجدول لا يحمل center_id ولا halaqah_id (التسميعات مثلاً
    تحمل student_id فقط)، فيُحصر بقائمة المعرّفات.
    """
    role = current_user.get("role")
    if role in GLOBAL_ROLES:
        return None
    if role in SELF_ROLES:
        return await own_student_ids(current_user)

    query = dict(NOT_DELETED)
    query["is_active"] = True
    if role in CENTER_ROLES:
        cid = current_user.get("center_id")
        if not cid:
            return []
        query["center_id"] = cid
    elif role in HALAQAH_ROLES:
        hids = await teacher_halaqah_ids(current_user)
        if not hids:
            return []
        query["halaqah_id"] = {"$in": hids}
    else:
        return []
    rows = await db.students.find(query, {"_id": 1}).to_list(20000)
    return [str(r["_id"]) for r in rows]


async def student_query(current_user: dict, base: Optional[dict] = None) -> Optional[dict]:
    """
    مرشِّح مجموعة students حسب نطاق المستخدم. None تعني «لا شيء مرئي».

    يُعاد None لا {} عند فراغ النطاق: المرشِّح الفارغ يعني «كل شيء»، وهو عكس
    المقصود تماماً — وهذا بالضبط نوع الخطأ الذي يفتح تسريباً وهو يبدو صحيحاً.
    """
    query = dict(base or {})
    role = current_user.get("role")

    if role in GLOBAL_ROLES:
        return query

    if role in CENTER_ROLES:
        cid = current_user.get("center_id")
        if not cid:
            return None
        query["center_id"] = cid
        return query

    if role in HALAQAH_ROLES:
        cid = current_user.get("center_id")
        hids = await teacher_halaqah_ids(current_user)
        if not cid or not hids:
            return None
        query["center_id"] = cid
        query["halaqah_id"] = {"$in": hids}
        return query

    if role in SELF_ROLES:
        sids = await own_student_ids(current_user)
        if not sids:
            return None
        from bson import ObjectId
        query["_id"] = {"$in": [ObjectId(s) for s in sids]}
        return query

    return None


async def assert_halaqah_in_scope(halaqah_id: str, current_user: dict) -> None:
    """يمنع قراءة حلقة خارج نطاق المستخدم (BOLA على مستوى الحلقة)."""
    hids = await visible_halaqah_ids(current_user)
    if hids is None:
        return
    if halaqah_id not in hids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذه الحلقة خارج نطاقك",
        )


def is_teacher_scoped(current_user: dict) -> bool:
    return current_user.get("role") in HALAQAH_ROLES


def teacher_only(current_user: dict, what: str = "هذا الإجراء") -> None:
    """
    يحصر فعلاً في شيخ الحلقة وحده.

    قرار المالك (2026-09-06): تسجيلُ التسميع والحضور شهادةٌ يؤدّيها من حضر
    المجلس. مديرُ المركز يقرأ كل شيء في مركزه ويُصحّح الخطأ بالتعديل والحذف،
    لكنه لا يُنشئ سجلّاً يشهد فيه على ما لم يحضره.
    """
    if current_user.get("role") not in HALAQAH_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{what} من عمل شيخ الحلقة وحده — المدير يُراجع ويُصحّح ولا يُسجّل",
        )


async def scoped_ids_set(current_user: dict) -> Optional[Set[str]]:
    ids = await visible_student_ids(current_user)
    return None if ids is None else set(ids)
