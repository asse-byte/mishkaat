"""
اختبارات دفعة 2026-09-07 — قرارات المالك.

    backend/.venv/Scripts/python.exe tests/owner_batch_2026_09_07_test.py

ما تحرسه:

    1. سلسلة المراسلة مغلقة: مدير النظام ⇄ مدير المركز ⇄ المعلّم، والطالب
       ووليّه يستقبلان من المدير. ولا يخاطب مديرُ النظام معلّماً ولا طالباً.
    2. الشهادات يُصدرها المدير وحده، بعد الاعتماد وبعد بلوغ المحطّة، ولا
       تُصدَر مرّتين.
    3. العمليات التي تقع مرّةً لا تُقبل مرّتين: تسميعُ اليوم، وراتبُ الشهر.
    4. وكلُّ عملٍ إداري يُصحَّح بعد وقوعه: الرسوم والرواتب والحضور والتسميع.
    5. الطالب يرى أقرانَ حلقته في لوحة الصدارة، ونتائجَ المسابقة كاملةً —
       ولا يفتح ملفَّ أحدٍ منهم.
    6. المعلّم يرى ترتيب حلقات المركز بالأرقام المجمّعة، ولا يفتح تفصيل
       حلقةٍ ليست له.
    7. نشاط المراكز لإدارة النظام يقيس الحركة لا الحجم.
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
    DB_NAME="mishkaat_owner_0907",
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

DBN = "mishkaat_owner_0907"
FAILS = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)


def blob(x):
    import json
    return json.dumps(x, ensure_ascii=False, default=str)


async def build():
    """مركز، حلقتان، أربعة طلاب — وأحدهم حافظٌ بلغ نصف القرآن."""
    await mongo.drop_database(DBN)
    from app.startup import startup_event
    await startup_event()
    now = utcnow()
    cid = str((await db.centers.insert_one(
        {"name": "مركز الاختبار", "is_active": True, "created_at": now})).inserted_id)

    async def user(u, role, center=cid, phone=None):
        return str((await db.users.insert_one({
            "username": u, "hashed_password": get_password_hash("Pass@1234"),
            "role": role, "center_id": center, "name": u, "phone": phone,
            "is_active": True, "created_at": now})).inserted_id)

    ids = {"center": cid}
    ids["mgr_user"] = await user("mgr", "center_manager")
    for tag in ("A", "B"):
        uid = await user(f"sheikh{tag}", "teacher")
        tid = str((await db.teachers.insert_one({
            "name": f"شيخ {tag}", "center_id": cid, "user_id": uid,
            "is_active": True})).inserted_id)
        hid = str((await db.halaqat.insert_one({
            "name": f"حلقة {tag}", "center_id": cid, "teacher_id": tid,
            "teacher_name": f"شيخ {tag}", "is_active": True})).inserted_id)
        sids = []
        for i in range(2):
            sid = str((await db.students.insert_one({
                "name": f"طالب {tag}{i}", "center_id": cid, "halaqah_id": hid,
                "halaqah_name": f"حلقة {tag}", "is_active": True,
                "student_type": "memorizing", "enrollment_date": now})).inserted_id)
            sids.append(sid)
            # تسميعاتٌ سابقة (أمس فما قبل) حتى لا تصطدم بحارس «مرّة في اليوم»
            for d in range(1, 4):
                past = now - timedelta(days=d)
                await db.recitations.insert_one({
                    "student_id": sid, "teacher_id": tid, "center_id": cid,
                    "surah_name": "البقرة", "start_ayah": 1, "end_ayah": 20,
                    "pages_count": 5, "evaluation": "good", "recitation_type": "new",
                    "date": past, "date_str": past.strftime("%Y-%m-%d"),
                    "error_tags": {"TAJ_ERR": 1}})
                await db.attendance.insert_one({
                    "student_id": sid, "halaqah_id": hid, "center_id": cid,
                    "status": "present", "date": past,
                    "date_str": past.strftime("%Y-%m-%d")})
        ids[tag] = {"user": uid, "teacher": tid, "halaqah": hid, "students": sids}

    # حافظٌ بلغ نصف القرآن: 310 صفحة تكفي لمحطّة «نصف القرآن» (15 جزءاً ≈ 302)
    hafidh = ids["A"]["students"][0]
    old = now - timedelta(days=40)
    await db.recitations.insert_one({
        "student_id": hafidh, "teacher_id": ids["A"]["teacher"], "center_id": cid,
        "surah_name": "دفعة حفظ", "start_ayah": 1, "end_ayah": 10,
        "pages_count": 310, "evaluation": "excellent", "recitation_type": "new",
        "date": old, "date_str": old.strftime("%Y-%m-%d"), "error_tags": {}})
    return ids


async def token(c, username, password="Pass@1234"):
    r = await c.post("/api/auth/login",
                     data={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def run():
    ids = await build()
    A, B = ids["A"], ids["B"]
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        MG = await token(c, "mgr")
        TA = await token(c, "sheikhA")
        TB = await token(c, "sheikhB")
        AD = await token(c, "admin", "Admin@12345")

        # ==================================================== 1. المراسلة
        print("--- سلسلة المراسلة مغلقة ---")
        r = await c.get("/api/messages/audiences", headers=AD)
        check("  مدير النظام لا يخاطب إلا مدراء المراكز",
              [a["value"] for a in r.json()["audiences"]] == ["center_manager"],
              blob(r.json()["audiences"]))
        r = await c.get("/api/messages/audiences", headers=TA)
        check("  والمعلّم لا يخاطب إلا مدير مركزه",
              [a["value"] for a in r.json()["audiences"]] == ["center_manager"],
              blob(r.json()["audiences"]))

        r = await c.post("/api/messages/broadcast", headers=AD, json={
            "recipient_role": "center_manager", "subject": "تعميم", "content": "نصّ"})
        check("  مدير النظام يُرسل (وكان يُردّ بـ400 لأنه بلا مركز)",
              r.status_code == 200, str(r.status_code))
        admin_msg = r.json().get("id")

        r = await c.get("/api/messages/inbox", headers=MG)
        check("  وتصل المدير", any(m["id"] == admin_msg for m in r.json()), "")
        r = await c.get("/api/messages/inbox", headers=TA)
        check("  ولا تصل المعلّم", not any(m["id"] == admin_msg for m in r.json()), "")

        for target in ("all_teachers", "student", "parent"):
            r = await c.post("/api/messages/broadcast", headers=AD, json={
                "recipient_role": target, "subject": "س", "content": "ص"})
            check(f"  مدير النظام → {target} ممنوع", r.status_code == 403,
                  str(r.status_code))

        r = await c.post("/api/messages/broadcast", headers=MG, json={
            "recipient_role": "admin", "subject": "طلب", "content": "نصّ"})
        check("  المدير يُراسل إدارة النظام", r.status_code == 200, str(r.status_code))
        mgr_msg = r.json().get("id")
        r = await c.get("/api/messages/inbox", headers=AD)
        check("  وتصلها", any(m["id"] == mgr_msg for m in r.json()), "")

        r = await c.post("/api/messages/broadcast", headers=TA, json={
            "recipient_role": "student", "subject": "س", "content": "ص"})
        check("  المعلّم → الطلاب ممنوع", r.status_code == 403, str(r.status_code))

        r = await c.put(f"/api/messages/{mgr_msg}", headers=TA, json={
            "recipient_role": "admin", "subject": "تحريف", "content": "ص"})
        check("  ولا يُصحّح رسالة غيره", r.status_code == 403, str(r.status_code))
        r = await c.put(f"/api/messages/{mgr_msg}", headers=MG, json={
            "recipient_role": "admin", "subject": "طلب (مصحّح)", "content": "ص"})
        check("  ويُصحّح المُرسِل رسالتَه", r.status_code == 200, str(r.status_code))
        r = await c.delete(f"/api/messages/{mgr_msg}", headers=MG)
        check("  ويسحبها", r.status_code == 200, str(r.status_code))

        # ==================================================== 2. الشهادات
        print()
        print("--- الشهادات: يُصدرها المدير وحده ---")
        hafidh = A["students"][0]
        r = await c.get("/api/certificates/eligible", headers=MG)
        pending = {s["student_id"]: [p["milestone"] for p in s["pending"]]
                   for s in r.json()["students"]}
        check("  الحافظ يظهر في المستحقّين", hafidh in pending, blob(list(pending)))
        check("  وتُعرض عليه محطّة نصف القرآن",
              "half" in pending.get(hafidh, []), blob(pending.get(hafidh)))

        r = await c.get("/api/certificates/eligible", headers=TA)
        check("  والمعلّم لا يفتح قائمة الإصدار → 403", r.status_code == 403,
              str(r.status_code))
        r = await c.post("/api/certificates/milestone", headers=TA,
                         json={"student_id": hafidh, "milestone": "half"})
        check("  ولا يُصدر شهادة → 403", r.status_code == 403, str(r.status_code))

        r = await c.post("/api/certificates/milestone", headers=MG,
                         json={"student_id": hafidh, "milestone": "half"})
        check("  المدير يُصدر", r.status_code == 200, str(r.status_code))
        cert = r.json()
        check("  ولها رقمٌ متسلسل", cert.get("serial", "").startswith("MK-"),
              cert.get("serial"))
        check("  ويُسجَّل من أصدرها", cert.get("issued_by_name") == "mgr",
              str(cert.get("issued_by_name")))

        r = await c.post("/api/certificates/milestone", headers=MG,
                         json={"student_id": hafidh, "milestone": "half"})
        check("  ولا تُصدَر مرّتين → 409", r.status_code == 409, str(r.status_code))

        r = await c.post("/api/certificates/milestone", headers=MG,
                         json={"student_id": B["students"][0], "milestone": "khatm"})
        check("  ولا تُصدَر لمن لم يبلغ المحطّة → 409", r.status_code == 409,
              str(r.status_code))

        # ==================================================== 3. منع التكرار
        print()
        print("--- ما يقع مرّةً لا يُقبل مرّتين ---")
        sid = A["students"][1]
        payload = {"student_id": sid, "teacher_id": "", "surah_name": "يس",
                   "start_ayah": 1, "end_ayah": 5, "evaluation": "good",
                   "recitation_type": "new", "error_tags": {}}
        r = await c.post("/api/recitations", headers=TA, json=payload)
        check("  تسميع الحفظ الأوّل اليوم", r.status_code == 200, str(r.status_code))
        rec_id = r.json().get("id")
        r = await c.post("/api/recitations", headers=TA, json=payload)
        check("  والثاني في اليوم نفسه → 409", r.status_code == 409, str(r.status_code))
        r = await c.post("/api/recitations", headers=TA,
                         json={**payload, "recitation_type": "review"})
        check("  لكن المراجعة نوعٌ آخر فتُقبل", r.status_code == 200, str(r.status_code))

        sal = {"teacher_id": A["teacher"], "amount": 100000,
               "month": "2026-09", "center_id": ids["center"]}
        r = await c.post("/api/salaries", headers=MG, json=sal)
        check("  راتب الشهر الأوّل", r.status_code == 200, str(r.status_code))
        sal_id = r.json().get("id")
        r = await c.post("/api/salaries", headers=MG, json=sal)
        check("  والثاني للشهر نفسه → 409", r.status_code == 409, str(r.status_code))
        r = await c.post("/api/salaries", headers=MG, json={**sal, "month": "2026-10"})
        check("  وشهرٌ آخر يُقبل", r.status_code == 200, str(r.status_code))

        # ==================================================== 4. التصحيح
        print()
        print("--- كلُّ عملٍ إداري يُصحَّح بعده ---")
        r = await c.put(f"/api/salaries/{sal_id}", headers=MG,
                        json={**sal, "amount": 120000})
        check("  تعديل مبلغ الراتب", r.status_code == 200 and r.json()["amount"] == 120000,
              str(r.status_code))
        r = await c.put(f"/api/salaries/{sal_id}", headers=MG,
                        json={**sal, "month": "2026-10"})
        check("  ونقلُه إلى شهرٍ مشغول → 409", r.status_code == 409, str(r.status_code))
        r = await c.delete(f"/api/salaries/{sal_id}", headers=MG,
                           params={"reason": "خطأ في التسجيل"})
        check("  وإلغاؤه بسبب", r.status_code == 200, str(r.status_code))
        r = await c.get("/api/salaries", headers=MG)
        check("  فيسقط من القائمة",
              not any(s["id"] == sal_id for s in r.json()), "")
        r = await c.post("/api/salaries", headers=MG, json=sal)
        check("  وبعد الإلغاء يُقبل الشهر من جديد", r.status_code == 200,
              str(r.status_code))

        fee = {"student_id": sid, "amount": 5000, "due_date": "2026-10-01",
               "fee_type": "monthly"}
        r = await c.post("/api/fees", headers=MG, json=fee)
        check("  إنشاء رسم", r.status_code == 200, str(r.status_code))
        fee_id = r.json()["id"]
        r = await c.post("/api/fees", headers=MG, json=fee)
        check("  ورسمٌ مكرّر لنفس الشهر → 409", r.status_code == 409, str(r.status_code))
        r = await c.put(f"/api/fees/{fee_id}", headers=MG, json={**fee, "amount": 7000})
        check("  تعديل مبلغ الرسم", r.status_code == 200, str(r.status_code))
        r = await c.delete(f"/api/fees/{fee_id}", headers=MG,
                           params={"reason": "سُجّل لطالبٍ آخر"})
        check("  وإلغاؤه", r.status_code == 200, str(r.status_code))
        r = await c.get("/api/finance/summary", headers=MG)
        check("  والملغى يسقط من المجاميع",
              r.json()["outstanding"]["fees_pending"] == 0,
              str(r.json()["outstanding"]))

        r = await c.get("/api/attendance", headers=TA)
        att_id = r.json()[0]["id"] if r.json() else None
        if att_id:
            r = await c.put(f"/api/attendance/{att_id}", headers=TA,
                            json={"status": "absent"})
            check("  تصحيح حالة حضور", r.status_code == 200, str(r.status_code))
            r = await c.put(f"/api/attendance/{att_id}", headers=TB,
                            json={"status": "present"})
            check("  ولا يُصحّح شيخٌ حضورَ حلقةٍ أخرى → 403", r.status_code == 403,
                  str(r.status_code))
            r = await c.delete(f"/api/attendance/{att_id}", headers=TA)
            check("  وحذف سجلٍّ رُصد خطأً", r.status_code == 200, str(r.status_code))

        if rec_id:
            r = await c.put(f"/api/recitations/{rec_id}", headers=TB,
                            json={**payload, "evaluation": "excellent"})
            check("  ولا يُعدّل شيخٌ تسميع زميله → 403", r.status_code == 403,
                  str(r.status_code))
            r = await c.put(f"/api/recitations/{rec_id}", headers=TA,
                            json={**payload, "evaluation": "excellent"})
            check("  ويُعدّل صاحبُه", r.status_code == 200, str(r.status_code))

        # ==================================================== 5. نطاق الطالب
        print()
        print("--- الطالب: أقرانُ حلقته والمسابقة كاملةً، بلا ملفّاتهم ---")
        r = await c.post(f"/api/students/{A['students'][0]}/accounts", headers=MG,
                         json={"holder": "student", "username": "talibA0",
                               "password": "Talib@1234"})
        check("  إصدار حساب الطالب", r.status_code == 200, str(r.status_code))
        r = await c.post("/api/auth/login",
                         data={"username": "talibA0", "password": "Talib@1234"})
        ST = {"Authorization": f"Bearer {r.json()['access_token']}"}

        r = await c.get("/api/performance/leaderboards", headers=ST)
        boards = r.json()["boards"]
        names = {e["name"] for b in boards for e in b["entries"]}
        check("  لوحة الصدارة فيها زملاء حلقته",
              "طالب A1" in names and "طالب A0" in names, blob(sorted(names)))
        check("  ولا أحدَ من حلقة (ب)",
              "طالب B0" not in names and "طالب B1" not in names, blob(sorted(names)))
        ranks = r.json()["own_ranks"]
        check("  ورتبتُه من أكثر من واحد",
              any((v or {}).get("of", 0) > 1 for v in ranks.values()), blob(ranks))

        r = await c.get(f"/api/students/{A['students'][1]}", headers=ST)
        check("  ولا يفتح ملفّ زميله → 403", r.status_code == 403, str(r.status_code))

        comp = await c.post("/api/competitions", headers=MG, json={
            "title": "مسابقة", "date": "2026-10-01",
            "judges": [{"teacher_id": A["teacher"]}]})
        comp_id = comp.json()["id"]
        for tag, who in (("A", A), ("B", B)):
            await c.post(f"/api/competitions/{comp_id}/register", headers=MG, json={
                "student_id": who["students"][0], "category": "جزء عمّ"})
        r = await c.get(f"/api/competitions/{comp_id}/contestants", headers=ST)
        body = blob(r.json())
        check("  ويرى متسابقي الحلقتين معاً (قرار المالك)",
              "طالب A0" in body and "طالب B0" in body, str(r.status_code))
        check("  والفروع الخمسة كلَّها", len(r.json()["branches"]) == 5,
              str(len(r.json()["branches"])))

        # ==================================================== 6. ترتيب الحلقات
        print()
        print("--- المعلّم يرى ترتيب الحلقات بأرقامٍ مجمّعة ---")
        r = await c.get("/api/halaqat-overview/ranking", headers=TA)
        rows = r.json()["halaqat"]
        check("  يرى الحلقتين", len(rows) == 2, str(len(rows)))
        check("  وحلقتُه مُعلَّمة", sum(1 for x in rows if x["is_mine"]) == 1,
              blob([(x["name"], x["is_mine"]) for x in rows]))
        body = blob(r.json())
        leaked = [n for n in ("طالب B0", "طالب B1", "طالب A0", "طالب A1") if n in body]
        check("  ولا اسمَ طالبٍ واحد في الجواب", not leaked, blob(leaked))
        other = next(x["id"] for x in rows if not x["is_mine"])
        r = await c.get(f"/api/halaqat-overview/{other}", headers=TA)
        check("  وتفصيل حلقة غيره ما زال محجوباً → 403", r.status_code == 403,
              str(r.status_code))

        # ==================================================== 7. نشاط المراكز
        print()
        print("--- نشاط المراكز: حركةٌ لا حجم ---")
        r = await c.get("/api/admin/centers-activity?days=30", headers=AD)
        check("  مدير النظام يقرؤه", r.status_code == 200, str(r.status_code))
        row = next((x for x in r.json()["centers"] if x["id"] == ids["center"]), None)
        check("  ويحسب تسميعات المركز", row and row["recitations"] > 0,
              str(row["recitations"]) if row else "—")
        check("  وحضورَه", row and row["attendance"] > 0,
              str(row["attendance"]) if row else "—")
        check("  ويُعطيه مستوى استخدام", bool(row and row["level"]),
              row["level"] if row else "—")
        r = await c.get("/api/admin/centers-activity", headers=MG)
        check("  ومدير المركز محجوب عنه → 403", r.status_code == 403, str(r.status_code))

        # ==================================================== 8. ورد المراجعة
        print()
        print("--- ورد المراجعة يُحسب من محفوظ كل طالب ---")
        r = await c.get("/api/review-plans/today", headers=TA)
        check("  المعلّم يقرأ ورد حلقته", r.status_code == 200, str(r.status_code))
        rows = r.json()["students"]
        check("  ولطلابه وحدهم",
              {x["student_name"] for x in rows} == {"طالب A0", "طالب A1"},
              blob([x["student_name"] for x in rows]))
        hz = next(x for x in rows if x["student_name"] == "طالب A0")
        check("  ووردُ الحافظ من محفوظه هو",
              hz["assignment"] and hz["assignment"]["memorized_juz"] > 10,
              blob(hz["assignment"]))
        check("  ودورتُه بعدد أجزائه",
              hz["assignment"]["cycle_days"] >= 15, blob(hz["assignment"]))
        r = await c.get("/api/review-plans/today", headers=ST)
        check("  والطالب يرى ورده وحده",
              [x["student_name"] for x in r.json()["students"]] == ["طالب A0"],
              blob([x["student_name"] for x in r.json()["students"]]))

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
