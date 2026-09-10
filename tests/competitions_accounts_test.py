"""
اختبارات دفعة 2026-09-06: المسابقات بلجنتها، وتقييم المحفّظ، وحسابات الطالب
ووليّه، ونظرة المدير على الحلقات.

    backend/.venv/Scripts/python.exe tests/competitions_accounts_test.py

ما تحرسه، وكلُّه قرارُ مالك صريح:

    1. الفروع منفصلة: ترتيبُ كل فرعٍ من واحد، وحافظُ جزء عمّ لا يُقارَن بحافظ
       القرآن كاملاً.
    2. لجنة تحكيم: كلُّ محكّمٍ يرصد درجتَه، والنهائيةُ متوسّطُها. ورصدُ الثاني
       لا يمحو رصدَ الأوّل — وهذا ما كان يقع.
    3. المعتمَدة مجمَّدة: لا رصدَ بعد الاعتماد ولا تسجيلَ ولا حذف.
    4. المسابقة لا تُفتح لشيخٍ ليس في لجنتها، وتختفي عنه بعد الاعتماد.
    5. الإدارة تعتمد ولا ترصد، والمحكّم يرصد ولا يعتمد.
    6. تقييمُ المحفّظ يقرؤه صاحبُه والمدير، لا زملاؤه.
    7. حساب الطالب ووليّه يُصدرهما المدير، ولا يريان إلا ما يخصّهما.
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
    DB_NAME="mishkaat_comp_test",
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

DBN = "mishkaat_comp_test"
FAILS = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)


def blob(x):
    import json
    return json.dumps(x, ensure_ascii=False, default=str)


async def build():
    """مركز، حلقتان بشيخيهما، وطالبان في كلٍّ."""
    await mongo.drop_database(DBN)
    from app.startup import startup_event
    await startup_event()
    now = utcnow()
    cid = str((await db.centers.insert_one({"name": "مركز", "is_active": True})).inserted_id)

    async def user(u, role, phone=None):
        return str((await db.users.insert_one({
            "username": u, "hashed_password": get_password_hash("Pass@1234"),
            "role": role, "center_id": cid, "name": u, "phone": phone,
            "is_active": True, "created_at": now})).inserted_id)

    await user("mgr", "center_manager")
    ids = {"center": cid}
    for tag in ("A", "B"):
        uid = await user(f"sheikh{tag}", "teacher")
        tid = str((await db.teachers.insert_one({
            "name": f"شيخ {tag}", "center_id": cid, "user_id": uid,
            "teacher_type": "halaqah", "is_active": True})).inserted_id)
        hid = str((await db.halaqat.insert_one({
            "name": f"حلقة {tag}", "center_id": cid, "teacher_id": tid,
            "teacher_name": f"شيخ {tag}", "schedule": "يومي", "is_active": True})).inserted_id)
        sids = []
        for i in range(2):
            sid = str((await db.students.insert_one({
                "name": f"طالب {tag}{i}", "center_id": cid, "halaqah_id": hid,
                "halaqah_name": f"حلقة {tag}", "is_active": True,
                "student_type": "memorizing"})).inserted_id)
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
        ids[tag] = {"user": uid, "teacher": tid, "halaqah": hid, "students": sids}
    return ids


async def token(c, username):
    r = await c.post("/api/auth/login",
                     data={"username": username, "password": "Pass@1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def run():
    ids = await build()
    A, B = ids["A"], ids["B"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        MG = await token(c, "mgr")
        TA = await token(c, "sheikhA")
        TB = await token(c, "sheikhB")

        # ==================================================== إنشاء المسابقة
        print("--- الإنشاء واللجنة ---")
        r = await c.get("/api/competitions/branches", headers=MG)
        branches = r.json()["branches"]
        check("  الفروع الخمسة قائمة مغلقة", len(branches) == 5, str(len(branches)))

        r = await c.post("/api/competitions", headers=TA, json={
            "title": "مسابقة الشيخ", "date": "2026-10-01"})
        check("  الشيخ لا يُنشئ مسابقة → 403", r.status_code == 403, str(r.status_code))

        r = await c.post("/api/competitions", headers=MG, json={
            "title": "المسابقة السنوية", "date": "2026-10-01",
            "branches": branches,
            "judges": [{"teacher_id": A["teacher"]}]})
        check("  المدير يُنشئ ويُعيّن اللجنة", r.status_code == 200, str(r.status_code))
        comp = r.json()
        check("  اسم المحكّم يُقرأ من السجلّ لا من الحمولة",
              comp["judges"][0]["teacher_name"] == "شيخ A", blob(comp["judges"]))
        check("  السنة تُشتقّ من التاريخ", comp["year"] == 2026, str(comp.get("year")))
        cmp_id = comp["id"]

        r = await c.post("/api/competitions", headers=MG, json={
            "title": "فرع مخترع", "date": "2026-10-02", "branches": ["نصف القرآن"]})
        check("  فرعٌ خارج القائمة المغلقة → 400", r.status_code == 400, str(r.status_code))

        # ==================================================== ظهور البند
        print()
        print("--- من يرى المسابقة أصلاً ---")
        r = await c.get("/api/competitions/my-role", headers=TA)
        check("  المحكّم: يظهر له البند", r.json()["can_see"] and r.json()["is_judge"],
              blob(r.json()))
        check("  my-role يُرجع سجلّ المحفّظ ليُعرف أيّ درجةٍ درجتُه",
              r.json()["teacher_id"] == A["teacher"], str(r.json().get("teacher_id")))
        # [قرار المالك 2026-09-10] غيرُ المحكّم يقرأ السجلّ ولا يرصد
        r = await c.get("/api/competitions/my-role", headers=TB)
        check("  غيرُ المحكّم: البند يظهر له",
              r.json()["can_see"] is True, blob(r.json()))
        check("  ولا يُوسَم محكّماً", r.json()["is_judge"] is False, blob(r.json()))
        r = await c.get("/api/competitions", headers=TB)
        check("  ويرى المسابقة في قائمته", len(r.json()) >= 1, str(len(r.json())))
        r = await c.get(f"/api/competitions/{cmp_id}/contestants", headers=TB)
        check("  ويفتح نتائجها", r.status_code == 200, str(r.status_code))

        # ==================================================== التسجيل
        print()
        print("--- تسجيل المتسابقين في الفروع ---")
        r = await c.post(f"/api/competitions/{cmp_id}/register", headers=MG, json={
            "student_id": A["students"][0], "category": "القرآن كاملاً"})
        check("  المدير يُسجّل في فرع", r.status_code == 200, str(r.status_code))
        c1 = r.json()["id"]
        r = await c.post(f"/api/competitions/{cmp_id}/register", headers=MG, json={
            "student_id": A["students"][1], "category": "القرآن كاملاً"})
        c2 = r.json()["id"]
        r = await c.post(f"/api/competitions/{cmp_id}/register", headers=MG, json={
            "student_id": B["students"][0], "category": "جزء عمّ"})
        c3 = r.json()["id"]

        r = await c.post(f"/api/competitions/{cmp_id}/register", headers=MG, json={
            "student_id": A["students"][0], "category": "5 أجزاء"})
        check("  الطالب لا يُسجَّل مرّتين → 400", r.status_code == 400, str(r.status_code))
        r = await c.post(f"/api/competitions/{cmp_id}/register", headers=MG, json={
            "student_id": B["students"][1], "category": "فرع لا وجود له"})
        check("  فرعٌ ليس في المسابقة → 400", r.status_code == 400, str(r.status_code))
        r = await c.post(f"/api/competitions/{cmp_id}/register", headers=TB, json={
            "student_id": B["students"][1], "category": "جزء عمّ"})
        check("  شيخٌ ليس محكّماً لا يُسجّل → 403", r.status_code == 403, str(r.status_code))

        # ==================================================== الرصد
        print()
        print("--- رصد اللجنة: كلٌّ درجتَه، والنهائيةُ متوسّطُها ---")
        r = await c.post(f"/api/competitions/contestants/{c1}/grade", headers=MG, json={
            "hifdh_score": 60, "tajweed_score": 18, "voice_score": 9})
        check("  الإدارة تعتمد ولا ترصد → 403", r.status_code == 403, str(r.status_code))
        r = await c.post(f"/api/competitions/contestants/{c1}/grade", headers=TB, json={
            "hifdh_score": 60, "tajweed_score": 18, "voice_score": 9})
        check("  غيرُ المحكّم لا يرصد → 403", r.status_code == 403, str(r.status_code))
        r = await c.post(f"/api/competitions/contestants/{c1}/grade", headers=TA, json={
            "hifdh_score": 80, "tajweed_score": 18, "voice_score": 9})
        check("  درجةٌ فوق السقف → 400", r.status_code == 400, str(r.status_code))

        r = await c.post(f"/api/competitions/contestants/{c1}/grade", headers=TA, json={
            "hifdh_score": 60, "tajweed_score": 18, "voice_score": 9})
        check("  المحكّم يرصد درجتَه", r.status_code == 200, str(r.status_code))
        check("  المجموع = 87 من محكّمٍ واحد", r.json()["total_score"] == 87.0,
              str(r.json()["total_score"]))
        check("  والرصد باسم صاحبه",
              r.json()["judge_scores"][0]["judge_name"] == "شيخ A",
              blob(r.json()["judge_scores"]))

        # محكّم ثانٍ يُضاف الآن ليُرصد بجانب الأوّل لا فوقه
        await c.put(f"/api/competitions/{cmp_id}", headers=MG, json={
            "judges": [{"teacher_id": A["teacher"]}, {"teacher_id": B["teacher"]}]})
        r = await c.post(f"/api/competitions/contestants/{c1}/grade", headers=TB, json={
            "hifdh_score": 50, "tajweed_score": 16, "voice_score": 7})
        check("  رصدُ الثاني لا يمحو رصدَ الأوّل", r.json()["judges_count"] == 2,
              str(r.json()["judges_count"]))
        check("  والنهائيةُ متوسّطُهما: (87 + 73) / 2 = 80",
              r.json()["total_score"] == 80.0, str(r.json()["total_score"]))
        r = await c.post(f"/api/competitions/contestants/{c1}/grade", headers=TB, json={
            "hifdh_score": 55, "tajweed_score": 16, "voice_score": 7})
        check("  وإعادةُ المحكّم لرصده تُصحّحه ولا تُضاعفه",
              r.json()["judges_count"] == 2, str(r.json()["judges_count"]))

        await c.post(f"/api/competitions/contestants/{c2}/grade", headers=TA, json={
            "hifdh_score": 68, "tajweed_score": 19, "voice_score": 10})
        await c.post(f"/api/competitions/contestants/{c3}/grade", headers=TA, json={
            "hifdh_score": 40, "tajweed_score": 12, "voice_score": 6})

        # ==================================================== الفصل بالفروع
        print()
        print("--- النتائج مفصولة بالفروع ---")
        r = await c.get(f"/api/competitions/{cmp_id}/contestants", headers=MG)
        blocks = {b["branch"]: b for b in r.json()["branches"]}
        check("  لكل فرعٍ كتلتُه", len(blocks) == 5, str(len(blocks)))
        full = blocks["القرآن كاملاً"]["contestants"]
        amma = blocks["جزء عمّ"]["contestants"]
        check("  فرع القرآن كاملاً فيه اثنان", len(full) == 2, str(len(full)))
        check("  وفرع جزء عمّ فيه واحد", len(amma) == 1, str(len(amma)))
        check("  الترتيب داخل الفرع يبدأ من واحد",
              [x["rank_in_branch"] for x in full] == [1, 2],
              str([x["rank_in_branch"] for x in full]))
        check("  الأعلى درجةً أوّلُ فرعه", full[0]["total_score"] >= full[1]["total_score"],
              str([x["total_score"] for x in full]))
        check("  حافظُ جزء عمّ أوّلُ فرعِه لا أخيرُ الجميع",
              amma[0]["rank_in_branch"] == 1, str(amma[0]["rank_in_branch"]))
        check("  واسمُ الحلقة يظهر مع المتسابق",
              amma[0]["halaqah_name"] == "حلقة B", str(amma[0].get("halaqah_name")))

        # ==================================================== الاعتماد والتجميد
        print()
        print("--- الاعتماد يُجمّد ---")
        r = await c.post(f"/api/competitions/{cmp_id}/approve", headers=TA)
        check("  المحكّم لا يعتمد → 403", r.status_code == 403, str(r.status_code))
        r = await c.post(f"/api/competitions/{cmp_id}/archive", headers=MG)
        check("  لا تُؤرشَف قبل الاعتماد → 409", r.status_code == 409, str(r.status_code))

        r = await c.post(f"/api/competitions/{cmp_id}/approve", headers=MG)
        check("  المدير يعتمد", r.status_code == 200, str(r.status_code))
        check("  ويُنبَّه إلى من بقي بلا درجة",
              r.json()["ungraded_contestants"] == 0, str(r.json()["ungraded_contestants"]))

        r = await c.post(f"/api/competitions/contestants/{c1}/grade", headers=TA, json={
            "hifdh_score": 70, "tajweed_score": 20, "voice_score": 10})
        check("  لا رصدَ بعد الاعتماد → 409", r.status_code == 409, str(r.status_code))
        r = await c.post(f"/api/competitions/{cmp_id}/register", headers=MG, json={
            "student_id": B["students"][1], "category": "جزء عمّ"})
        check("  ولا تسجيلَ بعده → 409", r.status_code == 409, str(r.status_code))
        r = await c.put(f"/api/competitions/{cmp_id}", headers=MG, json={"title": "تحريف"})
        check("  ولا تعديلَ للعنوان → 409", r.status_code == 409, str(r.status_code))
        r = await c.delete(f"/api/competitions/{cmp_id}", headers=MG)
        check("  ولا حذفَ: تُؤرشَف ولا تُمحى → 409", r.status_code == 409, str(r.status_code))

        # البندُ باقٍ (سجلٌّ يُقرأ)، وصفةُ التحكيم هي التي تسقط بالاعتماد
        r = await c.get("/api/competitions/my-role", headers=TA)
        check("  البند باقٍ للمعلّم بعد الاعتماد",
              r.json()["can_see"] is True, blob(r.json()))
        check("  وتسقط عنه صفةُ التحكيم فلا يرصد",
              r.json()["is_judge"] is False, blob(r.json()))

        r = await c.post(f"/api/competitions/{cmp_id}/archive", headers=MG)
        check("  الأرشفة بعد الاعتماد تمرّ", r.status_code == 200, str(r.status_code))
        r = await c.get("/api/competitions/years", headers=MG)
        check("  والسنة تُقرأ من الأرشيف", 2026 in r.json()["years"], blob(r.json()))
        r = await c.get("/api/competitions?year=2026", headers=MG)
        check("  ومسابقات السنة تُستعاد", len(r.json()) >= 1, str(len(r.json())))

        # ==================================================== تقييم المحفّظ
        print()
        print("--- تقييم المحفّظ بمعايير المالك ---")
        r = await c.post(f"/api/teachers/{A['teacher']}/evaluations", headers=MG, json={
            "teacher_id": A["teacher"], "evaluation_date": "2026-09-01",
            "performance": 9, "commitment": 8, "sincerity": 10,
            "seriousness": 9, "diligence": 8,
            "strengths": ["حضورٌ منتظم", "متابعةٌ لأولياء الأمور"],
            "weaknesses": ["تأخّرٌ في رفع التسميعات"]})
        check("  المدير يُقيّم", r.status_code == 200, str(r.status_code))
        check("  المجموع من 100 = مجموع المعايير × 2", r.json()["tpi"] == 88.0,
              str(r.json().get("tpi")))
        check("  ونقاط القوّة والضعف محفوظة",
              len(r.json()["strengths"]) == 2 and len(r.json()["weaknesses"]) == 1,
              blob(r.json().get("strengths")))
        check("  ويُسجَّل من قيّم", r.json()["evaluated_by"] == "mgr",
              str(r.json().get("evaluated_by")))

        r = await c.post(f"/api/teachers/{A['teacher']}/evaluations", headers=MG, json={
            "teacher_id": A["teacher"], "evaluation_date": "2026-09-02",
            "performance": 9, "commitment": 8})
        check("  تقييمٌ ناقص المعايير → 400", r.status_code == 400, str(r.status_code))

        r = await c.post(f"/api/teachers/{A['teacher']}/evaluations", headers=TB, json={
            "teacher_id": A["teacher"], "evaluation_date": "2026-09-01",
            "performance": 1, "commitment": 1, "sincerity": 1,
            "seriousness": 1, "diligence": 1})
        check("  والمحفّظ لا يُقيّم زميله → 403", r.status_code == 403, str(r.status_code))

        r = await c.get(f"/api/teachers/{A['teacher']}/evaluations", headers=TA)
        check("  المحفّظ يقرأ تقييم نفسه", r.status_code == 200 and len(r.json()) == 1,
              str(r.status_code))
        r = await c.get(f"/api/teachers/{A['teacher']}/evaluations", headers=TB)
        check("  ولا يقرأ تقييم زميله → 403", r.status_code == 403, str(r.status_code))

        # ==================================================== نظرة الحلقات
        print()
        print("--- نظرة المدير على الحلقات ---")
        r = await c.get("/api/halaqat-overview", headers=MG)
        check("  المدير يرى الحلقتين", len(r.json()["halaqat"]) == 2,
              str(len(r.json()["halaqat"])))
        check("  وعدد الطلاب أربعة", r.json()["totals"]["students"] == 4,
              str(r.json()["totals"]["students"]))
        r = await c.get("/api/halaqat-overview", headers=TA)
        rows = r.json()["halaqat"]
        check("  والشيخ يرى حلقتَه وحدها",
              len(rows) == 1 and rows[0]["name"] == "حلقة A", blob(rows))

        r = await c.get(f"/api/halaqat-overview/{B['halaqah']}", headers=MG)
        check("  تفصيل الحلقة: شيخُها وطلابُها",
              r.json()["teacher"]["name"] == "شيخ B" and len(r.json()["students"]) == 2,
              str(r.status_code))
        check("  ومقاييس كل طالب فيها", "mastery" in r.json()["students"][0],
              blob(list(r.json()["students"][0].keys())))
        r = await c.get(f"/api/halaqat-overview/{B['halaqah']}", headers=TA)
        check("  والشيخ لا يفتح تفصيل حلقة غيره → 403", r.status_code == 403,
              str(r.status_code))

        # ==================================================== الحسابات
        print()
        print("--- حسابا الطالب ووليّه يُصدرهما المدير ---")
        sid = A["students"][0]
        r = await c.get(f"/api/students/{sid}/accounts", headers=TA)
        check("  الشيخ لا يُصدر حسابات → 403", r.status_code == 403, str(r.status_code))

        r = await c.get(f"/api/students/{sid}/accounts", headers=MG)
        check("  لا حساب قبل الإصدار",
              r.json()["student_account"] is None and r.json()["parent_account"] is None,
              blob(r.json()))
        suggested = r.json()["suggested_password"]
        check("  ويُقترح كلمة مرور مستوفية", len(suggested) >= 8, suggested)

        r = await c.post(f"/api/students/{sid}/accounts", headers=MG, json={
            "holder": "student", "username": "talibA0", "password": "Talib@1234"})
        check("  إصدار حساب الطالب", r.status_code == 200, str(r.status_code))
        r = await c.post(f"/api/students/{sid}/accounts", headers=MG, json={
            "holder": "student", "username": "talibA0b", "password": "Talib@1234"})
        check("  ولا يُصدَر له ثانٍ → 409", r.status_code == 409, str(r.status_code))
        r = await c.post(f"/api/students/{sid}/accounts", headers=MG, json={
            "holder": "parent", "username": "waliA0"})
        check("  إصدار حساب وليّ الأمر بكلمة مرور مولَّدة",
              r.status_code == 200 and len(r.json()["password"]) >= 8, str(r.status_code))
        parent_pw = r.json()["password"]
        r = await c.post(f"/api/students/{A['students'][1]}/accounts", headers=MG, json={
            "holder": "student", "username": "talibA0"})
        check("  واسم مستخدمٍ مكرّر يُردّ → 400", r.status_code == 400, str(r.status_code))

        # ==================================================== نطاق الحسابين
        print()
        print("--- ولا يريان إلا ما يخصّهما ---")
        r = await c.post("/api/auth/login",
                         data={"username": "talibA0", "password": "Talib@1234"})
        check("  الطالب يدخل بحسابه", r.status_code == 200, str(r.status_code))
        ST = {"Authorization": f"Bearer {r.json()['access_token']}"}
        r = await c.post("/api/auth/login",
                         data={"username": "waliA0", "password": parent_pw})
        check("  ووليُّه يدخل بكلمته المولَّدة", r.status_code == 200, str(r.status_code))
        PR = {"Authorization": f"Bearer {r.json()['access_token']}"}

        for label, hdr in (("الطالب", ST), ("وليّ الأمر", PR)):
            r = await c.get("/api/students", headers=hdr)
            body = blob(r.json())
            leaked = [n for n in ("طالب A1", "طالب B0", "طالب B1") if n in body]
            check(f"  {label}: قائمة الطلاب هو وحده",
                  r.status_code == 200 and not leaked and "طالب A0" in body,
                  f"{r.status_code} {leaked}")
            r = await c.get(f"/api/students/{B['students'][0]}", headers=hdr)
            check(f"  {label}: ملفّ طالبٍ آخر → 403", r.status_code == 403,
                  str(r.status_code))
            r = await c.get(f"/api/performance/students/{sid}", headers=hdr)
            check(f"  {label}: يقرأ أداءه", r.status_code == 200, str(r.status_code))
            r = await c.get("/api/halaqat-overview", headers=hdr)
            check(f"  {label}: نظرة الحلقات محجوبة → 403", r.status_code == 403,
                  str(r.status_code))
            r = await c.get("/api/fees", headers=hdr)
            body = blob(r.json()) if r.status_code == 200 else ""
            check(f"  {label}: لا رسومَ لغيره",
                  all(n not in body for n in ("طالب A1", "طالب B0")), str(r.status_code))

        # وليّ الأمر مربوطٌ بالمعرّف لا بالهاتف: سجلّ الطالب هنا بلا parent_phone
        student_doc = await db.students.find_one({"name": "طالب A0"})
        check("  الربط بالمعرّف: parent_user_id مكتوب على الطالب",
              bool(student_doc.get("parent_user_id")), str(student_doc.get("parent_user_id")))
        check("  ويعمل بلا رقم هاتفٍ لوليّ الأمر",
              not student_doc.get("parent_phone"), str(student_doc.get("parent_phone")))

        # ==================================================== تغيير كلمة المرور
        print()
        print("--- ومن نسي كلمتَه تُبدَّل له ---")
        r = await c.post(f"/api/students/{sid}/accounts/reset", headers=MG,
                         json={"holder": "student"})
        check("  المدير يُبدّل كلمة مرور الطالب", r.status_code == 200, str(r.status_code))
        new_pw = r.json()["password"]
        r = await c.post("/api/auth/login",
                         data={"username": "talibA0", "password": "Talib@1234"})
        check("  والقديمة لم تعد تعمل", r.status_code == 401, str(r.status_code))
        r = await c.post("/api/auth/login",
                         data={"username": "talibA0", "password": new_pw})
        check("  والجديدة تعمل", r.status_code == 200, str(r.status_code))
        r = await c.post(f"/api/students/{B['students'][1]}/accounts/reset", headers=MG,
                         json={"holder": "parent"})
        check("  وحسابٌ لم يُصدَر → 404", r.status_code == 404, str(r.status_code))

    await mongo.drop_database(DBN)
    print()
    print("=" * 62)
    if FAILS:
        print(f"  فشل: {len(FAILS)}")
        for f in FAILS:
            print("   -", f)
    else:
        print("  ALL PASS")
    print("=" * 62)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
