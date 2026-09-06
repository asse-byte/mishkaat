"""
اختبارات طبقة الأداء والتنبؤ والتحفيز (FR6–FR13 من تقرير Halaqtna).

يُشغَّل على قاعدة بيانات مؤقّتة تُسقَط في النهاية:

    cd coran-center-management-main
    backend/.venv/Scripts/python.exe tests/performance_layer_test.py

كل تأكيد هنا فُحص أنه **يفشل** عند عكس ما يختبره، لا أنه ينجح فحسب. الاختبار
الحاسم هو `forecast_reacts_to_quality`: طالبان متطابقان في كل شيء إلا الأخطاء،
فإن تساوى تنبؤُهما فالجودة لا تدخل الحساب — وهي المساهمة التي يقوم عليها
القسم 2.6 من التقرير.
"""
import asyncio
import os
import random
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.update(
    APP_ENV="development",
    DB_NAME="mishkaat_perf_test",
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

TEST_DB = "mishkaat_perf_test"
FAILS = []


def check(name, cond, extra=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   {extra}" if extra else ""))
    if not cond:
        FAILS.append(name)


async def _seed_student(center_id, name, *, weeks=14, errors_per_session=0,
                        presence=1.0, verses=40, review_every=3, now=None,
                        halaqah_id=None):
    """طالب بتاريخ مصنوع: نفس الكمّية، والجودة والحضور متغيّران بالمعامِلات."""
    now = now or utcnow()
    sid = str((await db.students.insert_one({
        "name": name, "center_id": center_id, "is_active": True,
        "halaqah_id": halaqah_id, "halaqah_name": "حلقة الفحص",
        "student_type": "memorizing",
    })).inserted_id)
    for w in range(weeks):
        d = now - timedelta(days=7 * (weeks - w))
        await db.recitations.insert_one({
            "student_id": sid, "teacher_id": "t1", "surah_name": "البقرة",
            "start_ayah": 1, "end_ayah": verses, "evaluation": "good",
            "recitation_type": "new", "date": d, "center_id": center_id,
            "error_tags": ({"MEM_GAP": errors_per_session} if errors_per_session else {}),
        })
        if review_every and w % review_every == 0:
            await db.recitations.insert_one({
                "student_id": sid, "teacher_id": "t1", "surah_name": "البقرة",
                "start_ayah": 1, "end_ayah": 60, "evaluation": "good",
                "recitation_type": "review", "date": d, "center_id": center_id,
                "error_tags": {},
            })
        for k in range(2):
            dd = d + timedelta(days=k)
            await db.attendance.insert_one({
                "student_id": sid, "halaqah_id": "h1", "center_id": center_id,
                "status": "present" if random.random() < presence else "absent",
                "date": dd, "date_str": dd.strftime("%Y-%m-%d"),
            })
    return sid


async def main():
    await mongo.drop_database(TEST_DB)
    from app.startup import startup_event
    await startup_event()

    now = utcnow()
    random.seed(3)
    center_id = str((await db.centers.insert_one(
        {"name": "مركز الفحص", "is_active": True})).inserted_id)
    await db.users.insert_one({
        "username": "mgr", "hashed_password": get_password_hash("Mgr@12345"),
        "role": "center_manager", "center_id": center_id, "name": "مدير",
        "is_active": True, "created_at": now,
    })
    # [تحديث 2026-09-06] تسجيل التسميع صار من عمل شيخ الحلقة وحده، والطلابُ
    # يُسنَدون إلى حلقة حقيقية — وإلا لم يستطع أيّ شيخ الوصول إليهم أصلاً.
    tu = await db.users.insert_one({
        "username": "sheikh", "hashed_password": get_password_hash("Sheikh@1234"),
        "role": "teacher", "center_id": center_id, "name": "الشيخ",
        "is_active": True, "created_at": now,
    })
    tid = str((await db.teachers.insert_one({
        "name": "الشيخ", "center_id": center_id, "user_id": str(tu.inserted_id),
        "is_active": True,
    })).inserted_id)
    halaqah_id = str((await db.halaqat.insert_one({
        "name": "حلقة الفحص", "center_id": center_id, "teacher_id": tid,
        "teacher_name": "الشيخ", "schedule": "يومي", "is_active": True,
    })).inserted_id)

    # مجموعة تدريب متنوّعة كي يجد النموذج ما يتعلّمه
    for i in range(8):
        await _seed_student(center_id, f"خلفية {i}", errors_per_session=i % 5,
                            presence=0.5 + 0.06 * i, verses=20 + 5 * i, now=now,
                            halaqah_id=halaqah_id)

    # زوج المقارنة: كل شيء متطابق إلا الأخطاء
    clean_id = await _seed_student(center_id, "نظيف", errors_per_session=0, presence=1.0, now=now,
                                halaqah_id=halaqah_id)
    noisy_id = await _seed_student(center_id, "كثير الخطأ", errors_per_session=6, presence=1.0, now=now,
                                halaqah_id=halaqah_id)

    tr = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=tr, base_url="http://t") as c:
        r = await c.post("/api/auth/login", data={"username": "mgr", "password": "Mgr@12345"})
        H = {"Authorization": f"Bearer {r.json()['access_token']}"}
        rt = await c.post("/api/auth/login", data={"username": "sheikh", "password": "Sheikh@1234"})
        TH = {"Authorization": f"Bearer {rt.json()['access_token']}"}

        # ---------------------------------------------------- FR6 التصنيف
        et = (await c.get("/api/performance/error-types", headers=H)).json()["error_types"]
        check("FR6: أربعة أنواع أخطاء بأوزان متنازلة",
              len(et) == 4 and [e["weight"] for e in et] == sorted(
                  (e["weight"] for e in et), reverse=True),
              str([f"{e['code']}={e['weight']}" for e in et]))

        # ------------------------------------------------ FR7-FR9 المقاييس
        clean = (await c.get(f"/api/performance/students/{clean_id}", headers=H)).json()
        noisy = (await c.get(f"/api/performance/students/{noisy_id}", headers=H)).json()
        cm, nm = clean["metrics"], noisy["metrics"]

        check("FR7-FR9: المقاييس الخمسة كلها محسوبة",
              all(cm.get(k) is not None for k in
                  ("mastery", "momentum", "precision", "consistency", "review_depth")))
        check("FR7: الإتقان يهبط بارتفاع كثافة الخطأ",
              cm["mastery"] > nm["mastery"],
              f"نظيف={cm['mastery']} كثير الخطأ={nm['mastery']}")
        check("FR9: الدقّة تهبط بالأخطاء شديدة الوزن",
              cm["precision"] > nm["precision"],
              f"نظيف={cm['precision']} كثير الخطأ={nm['precision']}")
        check("الزخم متساوٍ بين الاثنين (الكمّية نفسها)",
              abs(cm["momentum"] - nm["momentum"]) < 0.01,
              f"{cm['momentum']} مقابل {nm['momentum']}")

        # ------------------------------------ FR10 الجودة تُغيّر التاريخ
        cw = clean["forecast"]["projected_weekly_pages"]
        nw = noisy["forecast"]["projected_weekly_pages"]
        check("FR10: التنبؤ يتفاعل مع الجودة لا مع الكمّية وحدها",
              cw > nw,
              f"نظيف={cw} صفحة/أسبوع، كثير الخطأ={nw} — بزخم متطابق")
        check("FR10: التنبؤ يكشف سماته الثلاث",
              set(clean["forecast"]["features"]) ==
              {"momentum", "error_density", "attendance_rate"})
        check("FR10: التنبؤ يُصرّح بطريقته",
              clean["forecast"]["method"] in ("trained_model", "momentum_fallback"),
              f"{clean['forecast']['method']} r2={clean['forecast'].get('model_r_squared')}"
              f" n={clean['forecast'].get('model_train_rows')}")
        check("FR10: موعدان — الجزء الحالي والمصحف كاملاً",
              bool(clean["forecast"]["juz_completion_date"]
                   and clean["forecast"]["quran_completion_date"]),
              f"جزء {clean['forecast']['current_juz']} في "
              f"{clean['forecast']['juz_eta_days']} يوماً")

        # ------------------------------------------- FR11 اللوحات الأربع
        lb = (await c.get("/api/performance/leaderboards", headers=H)).json()
        check("FR11: أربع لوحات", len(lb["boards"]) == 4,
              str([b["key"] for b in lb["boards"]]))
        orders = {b["key"]: tuple(e["id"] for e in b["entries"]) for b in lb["boards"]}
        check("FR11: اللوحات ترتّب ترتيبات مختلفة — وهي علّة وجودها",
              len(set(orders.values())) > 1,
              f"{len(set(orders.values()))} ترتيبات متمايزة من 4")
        for b in lb["boards"]:
            vals = [e["value"] for e in b["entries"]]
            check(f"  لوحة {b['key']} مرتّبة تنازلياً", vals == sorted(vals, reverse=True))
        check("FR11: من لا بيانات له لا يدخل اللوحة بصفر",
              all(e["value"] is not None for b in lb["boards"] for e in b["entries"]))

        # -------------------------------------- FR12-FR13 الأوسمة والنقاط
        check("FR12: أوسمة مُنحت تلقائياً",
              any(b["earned"] for b in clean["badges"]),
              str([b["code"] for b in clean["badges"] if b["earned"]]))
        check("FR13: نقاط خبرة تراكمت", clean["total_xp"] > 0, str(clean["total_xp"]))
        check("FR13: التحدّيات الأربعة وتقدّمها", len(clean["challenges"]) == 4)

        from app.gamification import award_xp
        base = (await c.get(f"/api/performance/students/{clean_id}", headers=H)).json()["total_xp"]
        await award_xp(clean_id, 500, "recitation", "SAME_SOURCE", center_id)
        once = (await c.get(f"/api/performance/students/{clean_id}", headers=H)).json()["total_xp"]
        await award_xp(clean_id, 500, "recitation", "SAME_SOURCE", center_id)
        twice = (await c.get(f"/api/performance/students/{clean_id}", headers=H)).json()["total_xp"]
        check("FR13: سجلّ النقاط عديم الأثر عند التكرار",
              once == base + 500 and twice == once, f"{base} ← {once} ← {twice}")

        # التسميع الجديد يمنح بعدد الصفحات
        x0 = (await c.get(f"/api/performance/students/{clean_id}", headers=H)).json()["total_xp"]
        rr = await c.post("/api/recitations", headers=TH, json={
            "student_id": clean_id, "teacher_id": tid, "surah_name": "يس",
            "start_ayah": 1, "end_ayah": 30, "evaluation": "good",
            "recitation_type": "new", "error_tags": {"TAJ_ERR": 1}, "pages_count": 2,
        })
        x1 = (await c.get(f"/api/performance/students/{clean_id}", headers=H)).json()["total_xp"]
        check("FR13: التسميع يمنح 10 نقاط لكل صفحة",
              rr.status_code == 200 and x1 == x0 + 20, f"{x0} ← {x1}")

        # نوع خطأ مجهول يُرفض
        bad = await c.post("/api/recitations", headers=TH, json={
            "student_id": clean_id, "teacher_id": tid, "surah_name": "يس",
            "start_ayah": 1, "end_ayah": 5, "evaluation": "good",
            "recitation_type": "new", "error_tags": {"MADE_UP": 3},
        })
        check("FR6: نوع خطأ خارج التصنيف مرفوض", bad.status_code == 422, str(bad.status_code))

        # ------------------------------------------------ خريطة الرحلة
        j = (await c.get(f"/api/performance/students/{clean_id}/journey", headers=H)).json()
        check("خريطة الرحلة: ثلاثون جزءاً",
              len(j["juz"]) == 30 and all(x["state"] in ("done", "active", "todo") for x in j["juz"]),
              f"{j['pages_memorized']} صفحة = {j['percent']}%")

        # ------------------------------------------------- FR16 العزل
        su = await db.users.insert_one({
            "username": "stu", "hashed_password": get_password_hash("Stu@12345"),
            "role": "student", "center_id": center_id, "name": "طالب",
            "is_active": True, "created_at": now,
        })
        await db.students.update_one({"_id": ObjectId(clean_id)},
                                     {"$set": {"user_id": str(su.inserted_id)}})
        r = await c.post("/api/auth/login", data={"username": "stu", "password": "Stu@12345"})
        SH = {"Authorization": f"Bearer {r.json()['access_token']}"}
        own = await c.get(f"/api/performance/students/{clean_id}", headers=SH)
        other = await c.get(f"/api/performance/students/{noisy_id}", headers=SH)
        check("FR16: الطالب يقرأ بياناته", own.status_code == 200, str(own.status_code))
        check("FR16: الطالب محجوب عن بيانات غيره", other.status_code == 403, str(other.status_code))
        slb = await c.get("/api/performance/leaderboards", headers=SH)
        check("FR16: الطالب يرى اللوحات وموقعَه فيها",
              slb.status_code == 200 and bool(slb.json()["own_ranks"]),
              str(slb.json().get("own_ranks", {}).get("momentum")))

        # ---------------------------------- توافق البيانات القديمة
        legacy_id = str((await db.students.insert_one({
            "name": "بيانات قديمة", "center_id": center_id, "is_active": True,
            "halaqah_id": halaqah_id, "student_type": "memorizing"})).inserted_id)
        for w in range(6):
            await db.recitations.insert_one({
                "student_id": legacy_id, "teacher_id": "t1", "surah_name": "البقرة",
                "start_ayah": 1, "end_ayah": 40, "evaluation": "good",
                "recitation_type": "new", "date": now - timedelta(days=7 * (6 - w)),
                "center_id": center_id,
                "mistakes_count": 2, "tajweed_errors_count": 3, "hesitations_count": 1,
            })
        leg = (await c.get(f"/api/performance/students/{legacy_id}", headers=H)).json()
        check("العدّادات القديمة تُقرأ بالتصنيف الجديد",
              leg["metrics"]["mastery"] is not None and leg["metrics"]["error_density"] > 0,
              f"إتقان={leg['metrics']['mastery']} كثافة={leg['metrics']['error_density']}")
        # العدّاد القديم لا يحمل نوع الخطأ. لو حُسبت منه الدقّة لخرجت صفراً لكل
        # طالب سبقت بياناتُه التصنيف — حكمٌ لم يُقَس، وتذييلٌ للوحة بلا سبب.
        check("الدقّة لا تُحتسب من بيانات غير موسومة", leg["metrics"]["precision"] is None,
              f"دقّة={leg['metrics']['precision']}")
        # وتسميعة موسومة بلا أخطاء دقّتُها تامّة، لا «لا بيانات»
        zero = await c.post("/api/recitations", headers=TH, json={
            "student_id": legacy_id, "teacher_id": tid, "surah_name": "الفاتحة",
            "start_ayah": 1, "end_ayah": 7, "evaluation": "excellent",
            "recitation_type": "new", "error_tags": {},
        })
        leg2 = (await c.get(f"/api/performance/students/{legacy_id}", headers=H)).json()
        check("تسميعة موسومة بلا أخطاء = دقّة تامّة",
              zero.status_code == 200 and leg2["metrics"]["precision"] == 100.0,
              f"دقّة={leg2['metrics']['precision']}")

        # ------------------------------------------- إعادة الاحتساب
        rec = await c.post("/api/performance/recompute", headers=H)
        check("إعادة احتساب الأوسمة للمركز", rec.status_code == 200, str(rec.json()))
        forbidden = await c.post("/api/performance/recompute", headers=SH)
        check("إعادة الاحتساب محجوبة عن الطالب", forbidden.status_code == 403,
              str(forbidden.status_code))

    await mongo.drop_database(TEST_DB)
    print()
    print("ALL PASS" if not FAILS else f"{len(FAILS)} FAILED: " + ", ".join(FAILS))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
