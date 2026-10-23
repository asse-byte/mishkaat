"""
«نسيت كلمة المرور؟» — استعادة بمساعدة المسؤول (2026-10-22).

    backend/.venv/Scripts/python.exe tests/forgot_password_2026_10_22_test.py

كان الزرّ بلا وظيفة، والرمز الذي يولّده /forgot-password لا يصل إلى أحد (لا SMS ولا
بريد). صار الطلب يصل إلى من يملك إعادة تعيين كلمة مرور صاحبه: مدير مركزه للطالب
ووليّ الأمر والمحفّظ، وإدارة النظام لمدير المركز. يعطيه المسؤول كلمة مرور مؤقتة،
فيُلزَم بتغييرها عند أوّل دخول.
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update(
    APP_ENV="development",
    DB_NAME="mishkaat_forgot_password_test",
    SEED_DEMO_DATA="false",
    PII_ENCRYPTION_KEY="8Wd1Q1kGh0kdN1c6bxlEBnGkVEyKk8IEwoP1DkCJ4Xo=",
    INITIAL_ADMIN_PASSWORD="Admin@12345",
    INITIAL_SUPER_ADMIN_PASSWORD="Super@12345",
)

import httpx  # noqa: E402

from app.clock import utcnow  # noqa: E402
from app.db import client as mongo, db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import get_password_hash  # noqa: E402

TEST_DB = "mishkaat_forgot_password_test"
FAILS = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)


async def main():
    await mongo.drop_database(TEST_DB)
    from app.startup import startup_event
    await startup_event()
    now = utcnow()

    cid = str((await db.centers.insert_one({"name": "مركز الإمام مالك", "is_active": True})).inserted_id)
    other = str((await db.centers.insert_one({"name": "مدرسة الفرقان", "is_active": True})).inserted_id)

    async def user(u, role, center, pw="Pass@1234"):
        return str((await db.users.insert_one({
            "username": u, "hashed_password": get_password_hash(pw), "role": role,
            "center_id": center, "name": u, "phone": "+223 70 00 00 00",
            "is_active": True, "created_at": now})).inserted_id)

    mgr = await user("mgr", "center_manager", cid)
    mgr2 = await user("mgr2", "center_manager", other)
    await user("sheikh", "teacher", cid)
    admin = str((await db.users.find_one({"role": "admin"}))["_id"])

    async def notes(uid):
        return await db.notifications.count_documents({"user_id": uid, "type": "password_help"})

    tr = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=tr, base_url="http://t") as c:
        async def token(u, pw="Pass@1234"):
            r = await c.post("/api/auth/login", data={"username": u, "password": pw})
            return r, ({"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else None)

        # ---------------------------------------------------- الطلب
        r1 = await c.post("/api/auth/forgot-password", json={"username": "sheikh"})
        r2 = await c.post("/api/auth/forgot-password", json={"username": "nobody"})
        check("الطلب يُقبل", r1.status_code == 200, str(r1.status_code))
        check("[أمن] الردّ واحد لاسمٍ موجود وغير موجود", r1.json() == r2.json(), r1.text[:80])
        check("الطلب محفوظ مفتوحاً",
              await db.password_help_requests.count_documents({"username": "sheikh", "resolved_at": None}) == 1)
        check("لا طلب لاسمٍ غير موجود", await db.password_help_requests.count_documents({"username": "nobody"}) == 0)
        check("مدير مركزه وصله إشعار", await notes(mgr) == 1)
        check("[أمن] مدير مركزٍ آخر لم يصله شيء", await notes(mgr2) == 0)
        check("وإدارة النظام لا تُشغَل بطلب محفّظ", await notes(admin) == 0)

        await c.post("/api/auth/forgot-password", json={"username": "sheikh"})
        check("التكرار لا يفتح طلباً ثانياً",
              await db.password_help_requests.count_documents({"username": "sheikh"}) == 1)
        check("  ولا يكرّر الإشعار", await notes(mgr) == 1)

        # ---------------------------------------------------- القائمة
        _, H_mgr = await token("mgr")
        _, H_mgr2 = await token("mgr2")
        _, H_teacher = await token("sheikh")
        rows = (await c.get("/api/auth/password-help-requests", headers=H_mgr)).json()
        check("مدير المركز يرى طلب محفّظه", [x["username"] for x in rows] == ["sheikh"], str(rows)[:120])
        req_id = rows[0]["id"] if rows else ""
        rows2 = (await c.get("/api/auth/password-help-requests", headers=H_mgr2)).json()
        check("[أمن] مدير مركزٍ آخر لا يراه", rows2 == [], str(rows2)[:80])
        rows_t = (await c.get("/api/auth/password-help-requests", headers=H_teacher)).json()
        check("المحفّظ لا قائمة له", rows_t == [])

        r = await c.post(f"/api/auth/password-help-requests/{req_id}/resolve", headers=H_mgr2)
        check("[أمن] مدير مركزٍ آخر ممنوع من معالجته", r.status_code == 403, str(r.status_code))

        # ---------------------------------------------------- المعالجة
        r = await c.post(f"/api/auth/password-help-requests/{req_id}/resolve", headers=H_mgr)
        temp = r.json().get("password", "")
        check("مدير المركز يصدر كلمة مرور مؤقتة", r.status_code == 200 and len(temp) >= 8, r.text[:100])
        r = await c.post(f"/api/auth/password-help-requests/{req_id}/resolve", headers=H_mgr)
        check("الطلب لا يُعالَج مرّتين", r.status_code == 404, str(r.status_code))
        r, _ = await token("sheikh")
        check("[أمن] كلمة المرور القديمة سقطت", r.status_code == 401, str(r.status_code))

        r, H_teacher = await token("sheikh", temp)
        check("يدخل بالمؤقتة", r.status_code == 200, str(r.status_code))
        check("  والدخول يقول إن عليه تغييرها", r.json()["user"].get("must_change_password") is True)
        me = (await c.get("/api/auth/me", headers=H_teacher)).json()
        check("  و/me كذلك", me.get("must_change_password") is True)

        r = await c.post("/api/auth/change-password", headers=H_teacher,
                         json={"current_password": temp, "new_password": "Sheikh2026"})
        check("يغيّرها", r.status_code == 200, r.text[:100])
        H_new = {"Authorization": f"Bearer {r.json()['access_token']}"}
        me = (await c.get("/api/auth/me", headers=H_new)).json()
        check("  فيرتفع الإلزام", me.get("must_change_password") is False, str(me)[:160])

        # ---------------------------------------------------- مدير المركز نفسه
        await c.post("/api/auth/forgot-password", json={"username": "mgr"})
        check("طلب مدير المركز يصل إلى إدارة النظام", await notes(admin) == 1)
        check("  لا إلى مدير مركزٍ آخر", await notes(mgr2) == 0)
        _, H_admin = await token("admin", "Admin@12345")
        rows = (await c.get("/api/auth/password-help-requests", headers=H_admin)).json()
        check("مدير النظام يراه", [x["username"] for x in rows] == ["mgr"], str(rows)[:120])

        # الطريق القديم يغلق الطلب المفتوح أيضاً
        r = await c.post("/api/auth/admin-reset-password", headers=H_admin,
                         json={"username": "mgr", "new_password": "Manager2026"})
        check("إعادة التعيين القديمة تعمل", r.status_code == 200, r.text[:100])
        rows = (await c.get("/api/auth/password-help-requests", headers=H_admin)).json()
        check("  وتغلق طلبه المفتوح", rows == [], str(rows)[:80])

    await mongo.drop_database(TEST_DB)
    print()
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: " + ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
