"""
اختبارات عزل البيانات بين الحلقات.

    backend/.venv/Scripts/python.exe tests/data_isolation_test.py

الخلل الذي دفع إليها: كان النظام يحصر بالمركز ولا يعرف الحلقة أصلاً. فشيخُ
الحلقة (أ) يقرأ كلَّ طلاب المركز — أسماءهم، وهواتفَ أوليائهم، وتسميعاتِهم،
وحضورَهم، ومقاييسَ أدائهم، وتاريخَ ختمهم المتوقَّع، ورسومَ المركز المالية —
ويستطيع تسجيل تسميع لطالب من حلقة (ب). سبعة عشر تسريباً من أصلٍ واحد.

النموذج المقصود:

    admin / super_admin   بلا حصر
    center_manager        مركزُه كاملاً قراءةً، ولا يُسجّل تسميعاً ولا حضوراً
    teacher               حلقاتُه وطلابُها وحدهم، قراءةً وكتابةً
    student / parent      نفسُه، واسم حلقته وشيخها، وموقعُه في لوحة الصدارة

كل تأكيد هنا يفحص **تسرّب بيانات الغير** لا مجرّد نجاح الطلب: أن يعود الطلب
بـ200 ليس خللاً؛ الخلل أن يعود ببيانات لا تخصّ صاحبَه.
"""
import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update(
    APP_ENV="development",
    DB_NAME="mishkaat_isolation_test",
    SEED_DEMO_DATA="false",
    PII_ENCRYPTION_KEY="8Wd1Q1kGh0kdN1c6bxlEBnGkVEyKk8IEwoP1DkCJ4Xo=",
    INITIAL_ADMIN_PASSWORD="Admin@12345",
    INITIAL_SUPER_ADMIN_PASSWORD="Super@12345",
)

import httpx  # noqa: E402
from bson import ObjectId  # noqa: E402

from app.clock import utcnow  # noqa: E402
from app.db import client as mongo, db  # noqa: E402
from app.main import app  # noqa: E402
from app.security import get_password_hash  # noqa: E402

DBN = "mishkaat_isolation_test"
FAILS = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)


async def build():
    """مركز واحد، حلقتان، لكلٍّ شيخُها وطالباها."""
    await mongo.drop_database(DBN)
    from app.startup import startup_event
    await startup_event()
    now = utcnow()
    cid = str((await db.centers.insert_one({"name": "مركز", "is_active": True})).inserted_id)

    async def user(u, role):
        return str((await db.users.insert_one({
            "username": u, "hashed_password": get_password_hash("Pass@1234"),
            "role": role, "center_id": cid, "name": u, "is_active": True,
            "created_at": now})).inserted_id)

    await user("mgr", "center_manager")
    ids = {"center": cid}
    for tag in ("A", "B"):
        uid = await user(f"sheikh{tag}", "teacher")
        tid = str((await db.teachers.insert_one({
            "name": f"شيخ {tag}", "center_id": cid, "user_id": uid,
            "is_active": True, "salary": 100000})).inserted_id)
        hid = str((await db.halaqat.insert_one({
            "name": f"حلقة {tag}", "center_id": cid, "teacher_id": tid,
            "teacher_name": f"شيخ {tag}", "schedule": "يومي", "is_active": True})).inserted_id)
        sids = []
        for i in range(2):
            sid = str((await db.students.insert_one({
                "name": f"طالب {tag}{i}", "center_id": cid, "halaqah_id": hid,
                "halaqah_name": f"حلقة {tag}", "is_active": True,
                "student_type": "memorizing", "phone": f"07{tag}0000{i}",
                "parent_phone": f"07{tag}9999{i}"})).inserted_id)
            sids.append(sid)
            await db.recitations.insert_one({
                "student_id": sid, "student_name": f"طالب {tag}{i}", "teacher_id": tid,
                "surah_name": "البقرة", "start_ayah": 1, "end_ayah": 20,
                "evaluation": "good", "recitation_type": "new",
                "date": now - timedelta(days=1), "center_id": cid,
                "error_tags": {"TAJ_ERR": 1}})
            d = now - timedelta(days=1)
            await db.attendance.insert_one({
                "student_id": sid, "halaqah_id": hid, "center_id": cid,
                "status": "present", "date": d, "date_str": d.strftime("%Y-%m-%d")})
            await db.fees.insert_one({
                "student_id": sid, "student_name": f"طالب {tag}{i}", "amount": 5000,
                "due_date": "2026-10-01", "fee_type": "monthly", "status": "pending",
                "center_id": cid})
        await db.academic_schedules.insert_one({
            "subject": f"مادة {tag}", "day": "الأحد", "time_slot": "08:00",
            "halaqa_id": hid, "teacher_id": tid, "center_id": cid,
            "teacher_name": f"شيخ {tag}", "created_at": now})
        ids[tag] = {"user": uid, "teacher": tid, "halaqah": hid, "students": sids}

    comp = str((await db.competitions.insert_one({
        "title": "مسابقة", "date": "2026-10-01", "categories": ["جزء عم"],
        "center_id": cid, "created_at": now})).inserted_id)
    for tag in ("A", "B"):
        await db.competition_contestants.insert_one({
            "competition_id": comp, "student_id": ids[tag]["students"][0],
            "student_name": f"طالب {tag}0", "category": "جزء عم",
            "total_score": 90, "center_id": cid, "created_at": now})
    ids["comp"] = comp

    stu_uid = await user("studA", "student")
    await db.students.update_one({"_id": ObjectId(ids["A"]["students"][0])},
                                 {"$set": {"user_id": stu_uid}})
    return ids


def blob(x):
    """كل نصوص الاستجابة في سلسلة واحدة، للبحث عن أثر بيانات الغير."""
    import json
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return str(x)


async def main():
    ids = await build()
    A, B = ids["A"], ids["B"]
    tr = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=tr, base_url="http://t") as c:
        async def tok(u, pw="Pass@1234"):
            r = await c.post("/api/auth/login", data={"username": u, "password": pw})
            return {"Authorization": f"Bearer {r.json()['access_token']}"}

        TA = await tok("sheikhA")
        MG = await tok("mgr")
        ST = await tok("studA")

        # ============================ شيخ الحلقة: لا يقرأ حلقة غيره
        print("--- شيخ الحلقة (أ) لا يصل إلى حلقة (ب) ---")
        for label, path in [
            ("ملفّ طالب", f"/api/students/{B['students'][0]}"),
            ("تسميعاته", f"/api/recitations/student/{B['students'][0]}"),
            ("حضوره", f"/api/attendance/student/{B['students'][0]}"),
            ("أداءه", f"/api/performance/students/{B['students'][0]}"),
            ("رحلته", f"/api/performance/students/{B['students'][0]}/journey"),
            ("تنبؤ ختمه", f"/api/analytics/predict/{B['students'][0]}"),
            ("تحليلاته", f"/api/analytics/student/{B['students'][0]}"),
            ("كشف حضور الحلقة", f"/api/attendance/halaqah/{B['halaqah']}"),
        ]:
            r = await c.get(path, headers=TA)
            check(f"  {label} → 403", r.status_code == 403, str(r.status_code))

        print("--- وقوائمه لا تحتوي على أثرٍ من حلقة (ب) ---")
        for label, path in [
            ("الطلاب", "/api/students"),
            ("الحلقات", "/api/halaqat"),
            ("التسميعات", "/api/recitations"),
            ("الحضور", "/api/attendance"),
            ("لوحات الصدارة", "/api/performance/leaderboards"),
            ("سجلّ الشرف", "/api/dashboard/honor-roll"),
            ("الترتيب الذكي", "/api/analytics/rankings"),
        ]:
            r = await c.get(path, headers=TA)
            body = blob(r.json())
            leaked = [n for n in ("طالب B0", "طالب B1", "حلقة B", "شيخ B") if n in body]
            check(f"  {label} خالية من بيانات (ب)", r.status_code == 200 and not leaked,
                  f"{r.status_code} {leaked}")

        r = await c.get("/api/dashboard/stats", headers=TA)
        check("  عدّاد الطلاب = طلاب حلقته (2) لا المركز (4)",
              r.json().get("total_students") == 2, str(r.json().get("total_students")))
        r = await c.get("/api/teachers", headers=TA)
        names = [t.get("name") for t in r.json()]
        check("  قائمة المحفّظين: نفسه وحده", names == ["شيخ A"], str(names))
        r = await c.get("/api/fees", headers=TA)
        check("  الرسوم المالية محجوبة عن المحفّظ", r.status_code == 403, str(r.status_code))

        print("--- ولا يكتب على ما ليس له ---")
        r = await c.post("/api/recitations", headers=TA, json={
            "student_id": B["students"][0], "teacher_id": A["teacher"],
            "surah_name": "يس", "start_ayah": 1, "end_ayah": 5,
            "evaluation": "good", "recitation_type": "new"})
        check("  تسميع لطالب من حلقة (ب) → 403", r.status_code == 403, str(r.status_code))
        r = await c.post("/api/attendance", headers=TA, json={"records": [
            {"student_id": B["students"][0], "halaqah_id": B["halaqah"], "status": "present"}]})
        check("  حضور لطالب من حلقة (ب) → 403", r.status_code == 403, str(r.status_code))

        print("--- لكنه يعمل على طلابه هو ---")
        r = await c.get(f"/api/students/{A['students'][0]}", headers=TA)
        check("  يقرأ ملفّ طالبه", r.status_code == 200, str(r.status_code))
        r = await c.post("/api/recitations", headers=TA, json={
            "student_id": A["students"][0], "teacher_id": A["teacher"],
            "surah_name": "يس", "start_ayah": 1, "end_ayah": 5,
            "evaluation": "good", "recitation_type": "new", "error_tags": {}})
        check("  يُسجّل تسميعاً لطالبه", r.status_code == 200, str(r.status_code))
        r = await c.post("/api/attendance", headers=TA, json={"records": [
            {"student_id": A["students"][0], "halaqah_id": A["halaqah"], "status": "present"}]})
        check("  يُسجّل حضور طالبه", r.status_code == 200, str(r.status_code))

        print("--- والأسطح الأخرى: الجدول، والمسابقة، والتقارير، والمالية ---")
        for label, path in [
            ("الجدول الدراسي", "/api/academic-schedules"),
            ("متسابقو المسابقة", f"/api/competitions/{ids['comp']}/contestants"),
        ]:
            r = await c.get(path, headers=TA)
            body = blob(r.json())
            leaked = [n for n in ("طالب B0", "حلقة B", "شيخ B", "مادة B") if n in body]
            check(f"  {label} بلا أثر من (ب)", r.status_code == 200 and not leaked,
                  f"{r.status_code} {leaked}")
        for label, path in [
            ("تصدير الطلاب", "/api/export/students.csv"),
            ("تصدير الحضور", "/api/export/attendance.csv"),
            ("الملخّص المالي", "/api/finance/summary"),
            ("الرواتب", "/api/salaries"),
            ("المصروفات", "/api/expenses"),
            ("سجلّ التدقيق", "/api/audit-logs"),
            ("تفاصيل المركز", f"/api/centers/{ids['center']}/details"),
        ]:
            r = await c.get(path, headers=TA)
            check(f"  {label} محجوب عن المحفّظ", r.status_code == 403, str(r.status_code))
        r = await c.post("/api/academic-schedules", headers=TA, json={
            "subject": "دسّ", "day": "الاثنين", "time_slot": "09:00",
            "halaqa_id": B["halaqah"], "teacher_id": A["teacher"], "center_id": ids["center"]})
        check("  حصّة في جدول حلقة (ب) → 403", r.status_code == 403, str(r.status_code))
        r = await c.post(f"/api/competitions/{ids['comp']}/register", headers=TA,
                         json={"student_id": B["students"][0], "category": "جزء عم"})
        check("  تسجيل طالب (ب) في مسابقة → 403", r.status_code == 403, str(r.status_code))

        # ============================ مدير المركز: يقرأ ولا يُسجّل
        print()
        print("--- مدير المركز: يرى مركزه كلَّه ---")
        r = await c.get("/api/students", headers=MG)
        check("  يرى الطلاب الأربعة", len(r.json()) == 4, str(len(r.json())))
        r = await c.get("/api/halaqat", headers=MG)
        check("  يرى الحلقتين", len(r.json()) == 2, str(len(r.json())))
        r = await c.get(f"/api/performance/students/{B['students'][0]}", headers=MG)
        check("  يقرأ أداء أيّ طالب في مركزه", r.status_code == 200, str(r.status_code))
        r = await c.get("/api/academic-schedules", headers=MG)
        check("  يرى جدول الحلقتين", len(r.json()) == 2, str(len(r.json())))
        r = await c.get(f"/api/competitions/{ids['comp']}/contestants", headers=MG)
        check("  يرى متسابقي الحلقتين", len(r.json()) == 2, str(len(r.json())))
        for label, path in [("الملخّص المالي", "/api/finance/summary"),
                            ("تصدير الطلاب", "/api/export/students.csv")]:
            r = await c.get(path, headers=MG)
            check(f"  {label} متاح له", r.status_code == 200, str(r.status_code))

        print("--- ولا يُسجّل ما هو من عمل الشيخ ---")
        r = await c.post("/api/recitations", headers=MG, json={
            "student_id": A["students"][0], "teacher_id": A["teacher"],
            "surah_name": "طه", "start_ayah": 1, "end_ayah": 5,
            "evaluation": "good", "recitation_type": "new"})
        check("  تسجيل التسميع → 403", r.status_code == 403,
              f"{r.status_code} {r.json().get('detail','')[:50]}")
        r = await c.post("/api/attendance", headers=MG, json={"records": [
            {"student_id": A["students"][0], "halaqah_id": A["halaqah"], "status": "present"}]})
        check("  تسجيل الحضور → 403", r.status_code == 403, str(r.status_code))

        print("--- لكنه يُصحّح ---")
        rec = await db.recitations.find_one({"student_id": A["students"][0]})
        r = await c.delete(f"/api/recitations/{rec['_id']}", headers=MG)
        check("  يحذف تسميعاً خاطئاً", r.status_code == 200, str(r.status_code))

        # ============================ الطالب
        print()
        print("--- الطالب: نفسُه وحلقتُه فقط ---")
        r = await c.get("/api/students", headers=ST)
        names = [s.get("name") for s in r.json()]
        check("  قائمة الطلاب = نفسه وحده", names == ["طالب A0"], str(names))
        r = await c.get(f"/api/students/{A['students'][1]}", headers=ST)
        check("  ملفّ زميله في حلقته → 403", r.status_code == 403, str(r.status_code))
        r = await c.get("/api/halaqat", headers=ST)
        hn = [h.get("name") for h in r.json()]
        check("  يرى حلقته وحدها", hn == ["حلقة A"], str(hn))
        r = await c.get("/api/teachers", headers=ST)
        check("  قائمة المحفّظين محجوبة", r.status_code == 403, str(r.status_code))
        r = await c.get("/api/fees", headers=ST)
        others = [f for f in r.json() if f.get("student_id") != A["students"][0]]
        check("  يرى رسومه وحدها", r.status_code == 200 and not others,
              f"{len(r.json())} رسم، منها {len(others)} لغيره")
        r = await c.get("/api/recitations", headers=ST)
        body = blob(r.json())
        check("  التسميعات: لا أثر لغيره",
              all(n not in body for n in ("طالب A1", "طالب B0", "طالب B1")), "")
        r = await c.get("/api/performance/leaderboards", headers=ST)
        body = blob(r.json())
        check("  لوحة الصدارة: زملاء حلقته نعم، وحلقة (ب) لا",
              "طالب B0" not in body and "طالب B1" not in body, "")
        for label, path in [
            ("الجدول الدراسي", "/api/academic-schedules"),
            ("متسابقو المسابقة", f"/api/competitions/{ids['comp']}/contestants"),
        ]:
            r = await c.get(path, headers=ST)
            body = blob(r.json())
            leaked = [n for n in ("طالب B0", "حلقة B", "شيخ B", "مادة B") if n in body]
            check(f"  {label} بلا أثر من (ب)", r.status_code == 200 and not leaked,
                  f"{r.status_code} {leaked}")
        for label, path in [
            ("خطط المراجعة", "/api/review-plans"),
            ("الملخّص المالي", "/api/finance/summary"),
            ("الرواتب", "/api/salaries"),
            ("المصروفات", "/api/expenses"),
            ("سجلّ التدقيق", "/api/audit-logs"),
            ("تفاصيل المركز", f"/api/centers/{ids['center']}/details"),
            ("تصدير الطلاب", "/api/export/students.csv"),
        ]:
            r = await c.get(path, headers=ST)
            check(f"  {label} محجوب عن الطالب", r.status_code == 403, str(r.status_code))
        r = await c.post("/api/messages/broadcast", headers=ST,
                         json={"recipient_role": "teacher", "subject": "ع", "content": "ن"})
        check("  بثّ رسالة → 403", r.status_code == 403, str(r.status_code))

    await mongo.drop_database(DBN)
    print()
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: " + ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
