"""
اختبارات ما ظهر أثناء تصوير السلسلة التعليمية (2026-10-22).

    backend/.venv/Scripts/python.exe tests/tutorial_findings_2026_10_22_test.py

ثلاثة أعطال كانت ظاهرةً على الشاشة لكل مستخدم، لا في حالةٍ طرفية:

1. اسم وليّ الأمر معمّى: الحساب يأخذ parent_name من سجلّ الطالب، وهو حقلٌ معمّى،
   فتقول لوحة وليّ الأمر «مرحباً بك، gAAAA…».
2. نسبة الحفظ صفرٌ دائماً: `progress` يُكتب صفراً عند التسجيل ولا يُحدَّث، فلوحة
   الطالب «0 / 30 جزءاً» ولوحة وليّه «الحفظ 0%» مهما سمّع.
3. أوّل ضبطٍ لمعدّل المراجعة يعود 500 — والخطة محفوظة فعلاً.
"""
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update(
    APP_ENV="development",
    DB_NAME="mishkaat_tutorial_findings_test",
    SEED_DEMO_DATA="false",
    PII_ENCRYPTION_KEY="8Wd1Q1kGh0kdN1c6bxlEBnGkVEyKk8IEwoP1DkCJ4Xo=",
    INITIAL_ADMIN_PASSWORD="Admin@12345",
    INITIAL_SUPER_ADMIN_PASSWORD="Super@12345",
)

import httpx  # noqa: E402

from app.clock import utcnow  # noqa: E402
from app.db import client as mongo, db  # noqa: E402
from app.main import app  # noqa: E402
from app.pii import encrypt_pii  # noqa: E402
from app.security import get_password_hash  # noqa: E402

TEST_DB = "mishkaat_tutorial_findings_test"
FAILS = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)


async def token(c, username):
    r = await c.post("/api/auth/login", data={"username": username, "password": "Pass@1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def main():
    await mongo.drop_database(TEST_DB)
    from app.startup import startup_event
    await startup_event()
    now = utcnow()

    cid = str((await db.centers.insert_one({"name": "مركز", "is_active": True})).inserted_id)

    async def user(u, role, **extra):
        return str((await db.users.insert_one({
            "username": u, "hashed_password": get_password_hash("Pass@1234"),
            "role": role, "center_id": cid, "name": u, "is_active": True,
            "created_at": now, **extra})).inserted_id)

    await user("mgr", "center_manager")
    t_uid = await user("sheikh", "teacher")
    tid = str((await db.teachers.insert_one({
        "name": "الشيخ", "center_id": cid, "user_id": t_uid, "is_active": True})).inserted_id)
    hid = str((await db.halaqat.insert_one({
        "name": "حلقة", "center_id": cid, "teacher_id": tid, "is_active": True})).inserted_id)

    tr = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=tr, base_url="http://t") as c:
        mgr = await token(c, "mgr")
        r = await c.post("/api/students", headers=mgr, json={
            "name": "موسى", "center_id": cid, "halaqah_id": hid, "halaqah_name": "حلقة",
            "parent_name": "الحاج لاسينا", "parent_phone": "+223 70 00 00 01"})
        sid = r.json()["id"]

        # ---------------------------------------------------- اسم وليّ الأمر
        raw = await db.students.find_one({"name": "موسى"})
        check("parent_name ما زال معمّى في القاعدة (الإصلاح لا يمسّ التعمية)",
              raw["parent_name"] != "الحاج لاسينا")
        r = await c.post(f"/api/students/{sid}/accounts", headers=mgr,
                         json={"holder": "parent", "username": "parent1", "password": "Pass@1234"})
        check("إصدار حساب وليّ الأمر", r.status_code == 200, str(r.status_code))
        u = await db.users.find_one({"username": "parent1"})
        check("اسم حساب وليّ الأمر صريح لا معمّى",
              u and u.get("name") == "الحاج لاسينا", repr((u or {}).get("name"))[:40])

        # حسابٌ قديم صدر قبل الإصلاح باسمٍ معمّى: يُفكّ عند الإقلاع
        await user("parent_old", "parent", **{"name": encrypt_pii("نانا ديارا")})
        await startup_event()
        u = await db.users.find_one({"username": "parent_old"})
        check("الاسم المعمّى القديم يُفكّ عند الإقلاع", u.get("name") == "نانا ديارا", repr(u.get("name"))[:40])
        await startup_event()
        u = await db.users.find_one({"username": "parent_old"})
        check("  والخطوة بلا أثر إن أُعيدت", u.get("name") == "نانا ديارا")

        # ---------------------------------------------------- نسبة الحفظ
        r = await c.get("/api/students", headers=mgr)
        s = next(x for x in r.json() if x["id"] == sid)
        check("طالبٌ بلا تسميع: الحفظ 0", s.get("progress") == 0, str(s.get("progress")))

        sheikh = await token(c, "sheikh")
        r = await c.post("/api/recitations", headers=sheikh, json={
            "student_id": sid, "teacher_id": "", "surah_name": "البقرة", "start_ayah": 1, "end_ayah": 50,
            "evaluation": "good", "recitation_type": "new", "pages_count": 60.4})
        check("تسميع حفظٍ جديد", r.status_code == 200, str(r.status_code))
        # مراجعةٌ في اليوم نفسه لا تُحسب حفظاً جديداً
        r = await c.post("/api/recitations", headers=sheikh, json={
            "student_id": sid, "teacher_id": "", "surah_name": "الفاتحة", "start_ayah": 1, "end_ayah": 7,
            "evaluation": "excellent", "recitation_type": "review", "pages_count": 100})
        check("تسميع مراجعة", r.status_code == 200, str(r.status_code))

        r = await c.get("/api/students", headers=mgr)
        s = next(x for x in r.json() if x["id"] == sid)
        check("الحفظ = صفحات الحفظ الجديد ÷ 604 (60.4 صفحة → 10%)",
              s.get("progress") == 10.0, str(s.get("progress")))
        check("السورة الحالية من آخر تسميع حفظ لا مراجعة",
              s.get("current_surah") == "البقرة" and s.get("current_ayah") == 50,
              f"{s.get('current_surah')} {s.get('current_ayah')}")
        r = await c.get(f"/api/students/{sid}", headers=mgr)
        check("ملفّ الطالب الواحد يحمل النسبة نفسها", r.json().get("progress") == 10.0,
              str(r.json().get("progress")))
        parent = await token(c, "parent1")
        r = await c.get("/api/students", headers=parent)
        check("ووليّ الأمر يراها في لوحته", r.status_code == 200 and r.json()
              and r.json()[0].get("progress") == 10.0, str(r.status_code))

        # ---------------------------------------------------- معدّل المراجعة
        r = await c.post("/api/review-plans", headers=sheikh, json={
            "center_id": cid, "student_id": sid, "juz_per_day": 0.5})
        check("أوّل ضبطٍ لمعدّل المراجعة يعود 200 لا 500", r.status_code == 200, str(r.status_code))
        check("  ويحمل معرّف الخطة", bool(r.json().get("id")) and "_id" not in r.json())

    await mongo.drop_database(TEST_DB)
    print()
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: " + ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
