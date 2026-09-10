"""
اختبارات دورة اعتماد المركز المسجَّل من الصفحة العامّة.

    backend/.venv/Scripts/python.exe tests/center_approval_test.py

الخلل الذي دفع إليها: من سجّل مركزه لم يستطع الدخول ورأى «الحساب معطّل» — وهي
رسالةُ حظرٍ لا رسالةُ انتظار. ولمّا دخل مديرُ النظام ليعتمده وجد قائمة المراكز
فارغة (كانت تحصر مدير النظام في مركزه، وهو دور عامّ بلا مركز)، ولم يجد زرّ
اعتماد أصلاً — فالنقطتان موجودتان في الخادم ولا تستدعيهما الواجهة.

النتيجة طريق مسدود كامل: لا صاحب المركز يدخل، ولا المدير يعتمد.
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update(
    APP_ENV="development",
    DB_NAME="mishkaat_approval_test",
    SEED_DEMO_DATA="false",
    PII_ENCRYPTION_KEY="8Wd1Q1kGh0kdN1c6bxlEBnGkVEyKk8IEwoP1DkCJ4Xo=",
    INITIAL_ADMIN_PASSWORD="Admin@12345",
    INITIAL_SUPER_ADMIN_PASSWORD="Super@12345",
    REGISTER_MAX_PER_WINDOW="20",
)

import httpx  # noqa: E402

from app.db import client as mongo, db  # noqa: E402
from app.main import app  # noqa: E402

TEST_DB = "mishkaat_approval_test"
FAILS = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)


def reg(username, name):
    return {
        "name": name, "address": "العنوان", "phone": "0500000000",
        "manager_name": "المدير", "manager_username": username,
        "manager_password": "Strong@123", "manager_email": f"{username}@example.com",
    }


async def main():
    await mongo.drop_database(TEST_DB)
    from app.startup import startup_event
    await startup_event()

    tr = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=tr, base_url="http://t") as c:
        r = await c.post("/api/auth/login", data={"username": "admin", "password": "Admin@12345"})
        AH = {"Authorization": f"Bearer {r.json()['access_token']}"}

        # مركز مسجَّل من الصفحة العامّة، وآخر يُنشئه المدير مباشرةً
        r1 = await c.post("/api/public/register-center", json=reg("m_pending", "مركز الانتظار"))
        r2 = await c.post("/api/public/register-center", json=reg("m_reject", "مركز الرفض"))
        check("تسجيلان عامّان ينجحان", r1.status_code == 200 and r2.status_code == 200,
              f"{r1.status_code}/{r2.status_code}")
        pending_id = r1.json()["id"]
        reject_id = r2.json()["id"]

        # -------------------------------- رسالة الدخول تُفرّق بين الحالتين
        r = await c.post("/api/auth/login", data={"username": "m_pending", "password": "Strong@123"})
        detail = r.json().get("detail", "")
        check("الحساب المعلَّق → 403", r.status_code == 403, str(r.status_code))
        check("الرسالة تقول «قيد المراجعة» لا «معطّل»",
              "قيد المراجعة" in detail and "معطّل" not in detail, detail[:60])

        # حساب معطَّل فعلاً (لا معلَّق) يبقى على رسالته
        await db.users.update_one({"username": "m_reject"},
                                  {"$set": {"approval_status": "suspended"}})
        r = await c.post("/api/auth/login", data={"username": "m_reject", "password": "Strong@123"})
        check("الحساب المعطَّل يبقى على رسالته المختلفة",
              r.status_code == 403 and "معطّل" in r.json().get("detail", ""),
              r.json().get("detail", "")[:50])
        await db.users.update_one({"username": "m_reject"},
                                  {"$set": {"approval_status": "pending"}})

        # -------------------------------- مدير النظام يرى ما يعتمده
        r = await c.get("/api/centers", headers=AH)
        names = [x["name"] for x in r.json()]
        check("مدير النظام يرى المراكز كلها بما فيها غير المفعَّلة",
              "مركز الانتظار" in names and "مركز الرفض" in names,
              f"{len(names)} مركز: {names}")

        r = await c.get("/api/centers/pending", headers=AH)
        check("الطابور يعرض الطلبين", len(r.json()) == 2, str(len(r.json())))

        # مدير مركز لا يرى إلا مركزه المفعَّل — الحصر لم يُفكّ عن غيره
        await db.users.update_one({"username": "m_pending"}, {"$set": {"is_active": True}})
        rr = await c.post("/api/auth/login", data={"username": "m_pending", "password": "Strong@123"})
        MH = {"Authorization": f"Bearer {rr.json()['access_token']}"}
        r = await c.get("/api/centers", headers=MH)
        check("مدير المركز ما زال محصوراً في مركزه", len(r.json()) <= 1, str(len(r.json())))
        await db.users.update_one({"username": "m_pending"}, {"$set": {"is_active": False}})

        # -------------------------------- الاعتماد يفتح الدخول
        r = await c.post(f"/api/centers/{pending_id}/approve", headers=AH)
        check("الاعتماد ينجح", r.status_code == 200, str(r.status_code))
        r = await c.post("/api/auth/login", data={"username": "m_pending", "password": "Strong@123"})
        check("صاحب المركز يدخل بعد الاعتماد", r.status_code == 200, str(r.status_code))
        if r.status_code == 200:
            check("ودورُه مدير مركز مفعَّل",
                  r.json()["user"]["role"] == "center_manager" and r.json()["user"]["is_active"],
                  str(r.json()["user"]["role"]))

        r = await c.get("/api/centers/pending", headers=AH)
        check("المعتمَد يخرج من الطابور", len(r.json()) == 1, str(len(r.json())))

        # -------------------------------- الرفض يُبقيه خارجاً
        r = await c.post(f"/api/centers/{reject_id}/reject", headers=AH)
        check("الرفض ينجح", r.status_code == 200, str(r.status_code))
        r = await c.post("/api/auth/login", data={"username": "m_reject", "password": "Strong@123"})
        check("المرفوض لا يدخل", r.status_code == 403, str(r.status_code))
        r = await c.get("/api/centers/pending", headers=AH)
        check("الطابور صار فارغاً", len(r.json()) == 0, str(len(r.json())))

        # -------------------------------- الصلاحية
        r = await c.get("/api/centers/pending", headers=MH)
        check("مدير المركز محجوب عن الطابور", r.status_code == 403, str(r.status_code))
        r = await c.post(f"/api/centers/{reject_id}/approve", headers=MH)
        check("مدير المركز لا يعتمد", r.status_code == 403, str(r.status_code))

    await mongo.drop_database(TEST_DB)
    print()
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: " + ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
