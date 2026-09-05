"""
اختبارات تسجيل مركز جديد من الصفحة العامّة.

    backend/.venv/Scripts/python.exe tests/register_center_test.py

الخلل الذي دفع إلى كتابتها: نموذج التسجيل في الواجهة لم يكن فيه حقلُ بريد
إلكتروني إطلاقاً، والخادم يشترطه — فكان كل طلب يعود 400، ثم يُمنع صاحبُه ساعةً
كاملة بـ429 لأن المحاولات الفاشلة كانت تستهلك حصّة الساعة. أي أن تسجيل مركز
جديد كان متعذّراً على كل أحد، لا في حالة طرفية.

التأكيد الحاسم هنا هو `الخطأ لا يستهلك الحصّة`: خمس محاولات فاشلة ثم واحدة
صحيحة يجب أن تنجح. لو عادت 429 فالحدّ يعاقب الخطأ المطبعي لا الإغراق.
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update(
    APP_ENV="development",
    DB_NAME="mishkaat_register_test",
    SEED_DEMO_DATA="false",
    PII_ENCRYPTION_KEY="8Wd1Q1kGh0kdN1c6bxlEBnGkVEyKk8IEwoP1DkCJ4Xo=",
    INITIAL_ADMIN_PASSWORD="Admin@12345",
    INITIAL_SUPER_ADMIN_PASSWORD="Super@12345",
    REGISTER_MAX_PER_WINDOW="3",
)

import httpx  # noqa: E402

from app.db import client as mongo, db  # noqa: E402
from app.main import app  # noqa: E402

TEST_DB = "mishkaat_register_test"
FAILS = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)


def payload(**over):
    base = {
        "name": "مركز الاختبار",
        "address": "العنوان",
        "phone": "0500000000",
        "manager_name": "المدير",
        "manager_username": "mgr_new",
        "manager_password": "Strong@123",
        "manager_email": "mgr@example.com",
    }
    base.update(over)
    return base


async def main():
    await mongo.drop_database(TEST_DB)
    from app.startup import startup_event
    await startup_event()

    tr = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=tr, base_url="http://t") as c:
        # ------------------------------------------------ التحقّق من المدخلات
        r = await c.post("/api/public/register-center", json=payload(manager_email=None))
        check("بلا بريد → 400 برسالة مفهومة", r.status_code == 400,
              f"{r.status_code} {r.json().get('detail', '')[:40]}")

        r = await c.post("/api/public/register-center", json=payload(manager_email="ليس بريداً"))
        check("بريد بصيغة خاطئة → 400", r.status_code == 400,
              f"{r.status_code} {r.json().get('detail', '')[:40]}")

        r = await c.post("/api/public/register-center", json=payload(manager_password="12345"))
        check("كلمة مرور قصيرة → 400", r.status_code == 400,
              f"{r.status_code} {r.json().get('detail', '')[:40]}")

        r = await c.post("/api/public/register-center", json=payload(manager_password="abcdefgh"))
        check("كلمة مرور بلا رقم → 400", r.status_code == 400,
              f"{r.status_code} {r.json().get('detail', '')[:40]}")

        r = await c.post("/api/public/register-center", json=payload(manager_username=""))
        check("بلا اسم مستخدم → 400", r.status_code == 400, str(r.status_code))

        # ---------------------- التأكيد الحاسم: الخطأ لا يستهلك حصّة الساعة
        # خمس محاولات فاشلة سبقت، والحدّ ثلاثة. لو كان الفشل يُحتسب لعادت 429.
        r = await c.post("/api/public/register-center", json=payload())
        check("بعد خمس محاولات فاشلة، الطلب الصحيح ينجح",
              r.status_code == 200, f"{r.status_code} {str(r.json())[:70]}")

        if r.status_code == 200:
            body = r.json()
            check("المركز يبدأ قيد المراجعة لا مفعَّلاً",
                  body.get("approval_status") == "pending", str(body.get("approval_status")))
            center = await db.centers.find_one({"_id": __import__("bson").ObjectId(body["id"])})
            check("المركز غير مفعَّل في قاعدة البيانات",
                  center.get("is_active") is False, str(center.get("is_active")))
            user = await db.users.find_one({"username": "mgr_new"})
            check("حساب المدير غير مفعَّل حتى الاعتماد",
                  user and user.get("is_active") is False, str(bool(user)))
            check("البريد محفوظ على الحساب",
                  user.get("email") == "mgr@example.com", str(user.get("email")))

        # ------------------------------------------------ الاسم المكرَّر
        r = await c.post("/api/public/register-center", json=payload())
        check("اسم مستخدم مأخوذ → 400 لا 500", r.status_code == 400,
              f"{r.status_code} {r.json().get('detail', '')[:40]}")

        # ------------------------------------------------ الحدّ يعمل فعلاً
        # نجح واحد. نُنجح اثنين آخرين فيبلغ الحدّ (3)، ثم يُردّ الرابع.
        for i in (2, 3):
            rr = await c.post("/api/public/register-center",
                              json=payload(manager_username=f"mgr_ok_{i}"))
            check(f"  تسجيل ناجح رقم {i}", rr.status_code == 200, str(rr.status_code))
        r = await c.post("/api/public/register-center", json=payload(manager_username="mgr_over"))
        check("الرابع في الساعة يُردّ 429 — الحدّ ما زال يردع الإغراق",
              r.status_code == 429, f"{r.status_code} {r.json().get('detail', '')[:40]}")

    await mongo.drop_database(TEST_DB)
    print()
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: " + ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
