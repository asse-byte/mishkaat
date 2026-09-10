"""
إصدار حسابات الطالب ووليّ أمره — بيد مدير المركز.

    GET  /api/students/{id}/accounts           ما أُصدر من حسابات (بلا كلمات مرور)
    POST /api/students/{id}/accounts           إصدار حساب الطالب و/أو وليّه
    POST /api/students/{id}/accounts/reset     تغيير كلمة مرور أحدهما

[قرار المالك 2026-09-06] الحساب يُصدَر **بعد** التسجيل لا معه: يُسجَّل الطالب
أوّلاً، ثمّ يُعطيه المدير اسمَ مستخدمٍ وكلمة مرور، وكذلك وليَّه.

والربطُ بالمعرّف: يُكتب `user_id` للطالب و`parent_user_id` لوليّه على سجلّ
الطالب، فحسابُ الابن وحسابُ الأب موصولان بهذا الطالب بعينه لا بمطابقة هاتفٍ
قد يتغيّر أو يُترك فارغاً — وهو أيضاً ما يجعل نطاقَهما لا يتجاوز ما يخصّهما.

كلمة المرور تُعرض **مرّة واحدة** في جواب الإصدار ليسلّمها المدير، ولا تُخزَّن
إلا مُعمّاة. ومن نسيها فليُصدر غيرها من `reset` — لا سبيل إلى استرجاعها،
وهذا مقصود.
"""

import secrets
import string
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.audit import write_audit_log
from app.clock import utcnow
from app.common import check_student_access, safe_object_id
from app.db import db
from app.security import (
    get_current_user,
    get_password_hash,
    validate_password_complexity,
)

router = APIRouter(tags=["حسابات الطلاب وأولياء الأمور"])

MANAGERS = ("admin", "super_admin", "center_manager")
Holder = Literal["student", "parent"]

# بلا أحرفٍ يلتبس بعضها ببعض على ورقةٍ مكتوبة بخطّ اليد: O و0، l و1 و I.
_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
_DIGITS = "23456789"


def _suggest_password(length: int = 10) -> str:
    """كلمة مرور تُملى وتُكتب بلا لبس، وتستوفي شرط الحرف والرقم."""
    body = "".join(secrets.choice(_ALPHABET + _DIGITS) for _ in range(length - 2))
    return secrets.choice(_ALPHABET) + body + secrets.choice(_DIGITS)


class AccountRequest(BaseModel):
    holder: Holder
    username: str
    password: Optional[str] = None   # يُولَّد إن تُرك فارغاً
    name: Optional[str] = None


class ResetRequest(BaseModel):
    holder: Holder
    password: Optional[str] = None


def _require_manager(current_user: dict) -> None:
    if current_user["role"] not in MANAGERS:
        raise HTTPException(
            status_code=403,
            detail="إصدار الحسابات من عمل مدير المركز")


async def _user_brief(user_id: Optional[str]) -> Optional[dict]:
    if not user_id:
        return None
    u = await db.users.find_one({"_id": safe_object_id(user_id)})
    if not u:
        return None
    return {
        "id": str(u["_id"]),
        "username": u.get("username"),
        "name": u.get("name"),
        "role": u.get("role"),
        "is_active": u.get("is_active", True),
    }


@router.get("/api/students/{student_id}/accounts")
async def get_accounts(student_id: str, current_user: dict = Depends(get_current_user)):
    """ما أُصدر لهذا الطالب ووليّه من حسابات — أسماء المستخدمين لا كلمات المرور."""
    _require_manager(current_user)
    student = await check_student_access(student_id, current_user)
    return {
        "student_id": student_id,
        "student_name": student.get("name"),
        "parent_name": student.get("parent_name"),
        "parent_phone": student.get("parent_phone"),
        "student_account": await _user_brief(student.get("user_id")),
        "parent_account": await _user_brief(student.get("parent_user_id")),
        "suggested_password": _suggest_password(),
    }


@router.post("/api/students/{student_id}/accounts")
async def issue_account(student_id: str, req: AccountRequest,
                        current_user: dict = Depends(get_current_user)):
    """إصدار حساب للطالب أو لوليّ أمره، وربطُه بسجلّ الطالب."""
    _require_manager(current_user)
    student = await check_student_access(student_id, current_user)

    field = "user_id" if req.holder == "student" else "parent_user_id"
    if student.get(field):
        raise HTTPException(
            status_code=409,
            detail="لهذا الحساب مالكٌ بالفعل — غيّر كلمة المرور بدل إصدار حسابٍ ثانٍ")

    username = (req.username or "").strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="اسم المستخدم ثلاثة أحرف فأكثر")
    if await db.users.find_one({"username": username}):
        raise HTTPException(status_code=400, detail="اسم المستخدم مستعمل")

    password = req.password or _suggest_password()
    validate_password_complexity(password)

    if req.holder == "student":
        name = req.name or student.get("name")
        phone = student.get("phone")
    else:
        name = req.name or student.get("parent_name") or f"وليّ أمر {student.get('name')}"
        phone = student.get("parent_phone")

    user_doc = {
        "username": username,
        "name": name,
        "role": req.holder,
        "center_id": student.get("center_id"),
        "phone": phone,
        "hashed_password": get_password_hash(password),
        "is_active": True,
        "user_version": 0,
        "created_at": utcnow(),
    }
    res = await db.users.insert_one(user_doc)
    uid = str(res.inserted_id)

    await db.students.update_one(
        {"_id": safe_object_id(student_id)},
        {"$set": {field: uid}})

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=student.get("center_id", "system"),
        action="ACCOUNT_ISSUED",
        payload={"student_id": student_id, "holder": req.holder, "username": username})

    return {
        "message": "أُصدر الحساب ورُبط بالطالب",
        "holder": req.holder,
        "username": username,
        # تُعرض مرّة واحدة ليسلّمها المدير، ولا تُخزَّن إلا مُعمّاة
        "password": password,
        "user_id": uid,
    }


@router.post("/api/students/{student_id}/accounts/reset")
async def reset_account_password(student_id: str, req: ResetRequest,
                                 current_user: dict = Depends(get_current_user)):
    """كلمة مرور جديدة لحسابٍ صادر — لمن نسيها."""
    _require_manager(current_user)
    student = await check_student_access(student_id, current_user)

    field = "user_id" if req.holder == "student" else "parent_user_id"
    uid = student.get(field)
    if not uid:
        raise HTTPException(status_code=404, detail="لا حساب مُصدَراً لهذا الشخص")

    password = req.password or _suggest_password()
    validate_password_complexity(password)

    # رفعُ user_version يُبطل الجلسات القائمة: من غُيّرت كلمتُه يخرج من كل جهاز.
    await db.users.update_one(
        {"_id": safe_object_id(uid)},
        {"$set": {"hashed_password": get_password_hash(password)},
         "$inc": {"user_version": 1}})

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=student.get("center_id", "system"),
        action="ACCOUNT_PASSWORD_RESET",
        payload={"student_id": student_id, "holder": req.holder})

    return {"message": "غُيّرت كلمة المرور", "holder": req.holder, "password": password}
