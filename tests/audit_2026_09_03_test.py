"""
اختبار انحدار لإصلاحات مراجعة 2026-09-03 على Mishkaat backend/server.py

كل فحص هنا يثبّت إصلاحاً بعينه: أُعيد كل واحد منها إلى حاله قبل الإصلاح وتُحقِّق أن الفحص
يفشل فعلاً — فحص لا يفشل عند إرجاع الخلل لا يحمي شيئاً.

التشغيل (يحتاج MongoDB على المنفذ الافتراضي):
    cd backend
    .venv/Scripts/python.exe ../tests/audit_2026_09_03_test.py

يُنشئ قاعدة بيانات مؤقتة mishkaat_audit_test ويحذفها في النهاية، ولا يمسّ بيانات الإنتاج.
"""
import os, sys, gc, asyncio

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DB = "mishkaat_audit_test"
os.environ.update({
    "APP_ENV": "development",
    "DB_NAME": DB,
    "MONGO_URL": "mongodb://localhost:27017",
    "SEED_DEMO_DATA": "false",
    "INITIAL_ADMIN_PASSWORD": "AdminTest1234",
    "INITIAL_SUPER_ADMIN_PASSWORD": "SuperTest1234",
    "PII_ENCRYPTION_KEY": "8Wd1Q1kGh0kdN1c6bxlEBnGkVEyKk8IEwoP1DkCJ4Xo=",
    "SECRET_KEY": "a" * 128,
    "TRUST_PROXY": "true",
})

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

import httpx
import server

PASSED, FAILED = [], []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"   [{detail}]" if detail and not cond else ""))


async def login(c, u, p):
    r = await c.post("/api/auth/login", data={"username": u, "password": p})
    if r.status_code != 200:
        return None, r
    return r.json()["access_token"], r


def H(t):
    return {"Authorization": f"Bearer {t}"}


async def main():
    await server.client.drop_database(DB)
    await server.startup_event()

    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:

        # ---------- bootstrap ----------
        admin, _ = await login(c, "admin", "AdminTest1234")
        check("admin يسجّل الدخول", admin is not None)

        sa_tok, r_sa = await login(c, "superadmin", "SuperTest1234")
        check("superadmin بكلمة المرور من البيئة", sa_tok is not None)

        bad, _ = await login(c, "superadmin", "superadmin123")
        check("[أمن] كلمة المرور الثابتة superadmin123 لم تعد صالحة", bad is None)

        # ---------- center + users ----------
        r = await c.post("/api/centers", headers=H(admin), json={
            "name": "مركز الاختبار", "address": "باماكو",
            "manager_username": "mgr1", "manager_password": "Manager1234",
            "manager_name": "مدير", "manager_email": "m@x.com"})
        check("إنشاء مركز + حساب مدير", r.status_code == 200, r.text[:120])
        center_id = r.json()["id"]
        mgr, _ = await login(c, "mgr1", "Manager1234")

        # معلّم بالراتب — الحقل كان يُهمَل عند الإنشاء
        r = await c.post("/api/teachers", headers=H(mgr), json={
            "name": "الشيخ أحمد", "center_id": center_id, "salary": 75000,
            "marital_status": "married", "work_schedule": "full_time",
            "username": "teach1", "password": "Teacher1234"})
        check("[خلل] الراتب يُحفَظ عند إنشاء المعلم", r.json().get("salary") == 75000, str(r.json()))
        teacher_id = r.json()["id"]

        r = await c.post("/api/halaqat", headers=H(mgr), json={
            "name": "حلقة الفجر", "center_id": center_id, "schedule": "يومياً",
            "teacher_id": teacher_id, "teacher_name": "الشيخ أحمد"})
        halaqah_id = r.json()["id"]

        r = await c.post("/api/students", headers=H(mgr), json={
            "name": "طالب أول", "center_id": center_id, "halaqah_id": halaqah_id,
            "parent_name": "أبو الطالب", "parent_phone": "+22370000001", "phone": "+22371111111"})
        student_id = r.json()["id"]
        r = await c.post("/api/students", headers=H(mgr), json={
            "name": "طالب ثانٍ", "center_id": center_id, "halaqah_id": halaqah_id,
            "parent_name": "أبو الثاني", "parent_phone": "+22370000002"})
        student2_id = r.json()["id"]

        # حسابا وليّ أمر وطالب
        await server.db.users.insert_one({
            "username": "parent1", "name": "أبو الطالب", "role": "parent",
            "phone": "+22370000001", "hashed_password": server.get_password_hash("Parent1234"),
            "is_active": True, "user_version": 0, "created_at": server.datetime.utcnow()})
        await server.db.users.insert_one({
            "username": "intruder", "name": "دخيل", "role": "parent",
            "phone": "+22379999999", "hashed_password": server.get_password_hash("Intruder1234"),
            "is_active": True, "user_version": 0, "created_at": server.datetime.utcnow()})
        parent, _ = await login(c, "parent1", "Parent1234")
        intruder, _ = await login(c, "intruder", "Intruder1234")

        # ---------- 1. تصعيد الصلاحيات عبر الملف الشخصي ----------
        r = await c.put("/api/auth/profile", headers=H(intruder), json={"phone": "+22370000002"})
        check("[أمن] وليّ أمر لا يستطيع انتحال رقم هاتف أسرة أخرى", r.status_code == 403, r.text[:120])

        r = await c.get(f"/api/students/{student2_id}", headers=H(intruder))
        check("[أمن] الدخيل ممنوع من ملف الطالب", r.status_code == 403, str(r.status_code))

        r = await c.get("/api/students", headers=H(parent))
        names = [s["name"] for s in r.json()]
        check("وليّ الأمر يرى ابنه فقط", names == ["طالب أول"], str(names))

        # ---------- 2. رموز إعادة التعيين ----------
        r = await c.post("/api/auth/forgot-password", json={"username": "superadmin"})
        check("طلب إعادة التعيين يُقبل بلا تسريب", r.status_code == 200)
        stored = await server.db.password_resets.find_one({"username": "superadmin"})
        check("[أمن] الرمز مخزَّن مبصوماً لا صريحاً",
              stored is not None and "code" not in stored and "code_hash" in stored, str(stored))

        r = await c.get("/api/auth/reset-codes", headers=H(mgr))
        check("[أمن] مدير المركز محجوب عن قائمة رموز إعادة التعيين", r.status_code == 403, str(r.status_code))

        r = await c.get("/api/auth/reset-codes", headers=H(admin))
        leaked = any("code" in row for row in r.json())
        check("[أمن] القائمة لا تُرجع أي رمز حتى للمدير", r.status_code == 200 and not leaked, r.text[:150])

        for i in range(6):
            rr = await c.post("/api/auth/reset-password", json={
                "username": "superadmin", "code": f"00000{i}", "new_password": "Hacked1234"})
        check("[أمن] تخمين الرمز يُقفل بعد 5 محاولات", rr.status_code == 429, str(rr.status_code))
        still, _ = await login(c, "superadmin", "SuperTest1234")
        check("[أمن] حساب المدير العام لم يُخترق", still is not None)

        # مدير المركز لا يعيد تعيين كلمة مرور حساب إداري
        r = await c.post("/api/auth/admin-reset-password", headers=H(mgr),
                         json={"username": "superadmin", "new_password": "Whatever1234"})
        check("[أمن] مدير المركز ممنوع من إعادة تعيين حساب المدير العام", r.status_code == 403, str(r.status_code))

        # ---------- 3. كشف الرواتب ----------
        teach, _ = await login(c, "teach1", "Teacher1234")
        r = await c.get("/api/teachers", headers=H(teach))
        check("[أمن] المعلم لا يرى رواتب زملائه",
              all("salary" not in t for t in r.json()), r.text[:160])
        r = await c.get("/api/teachers", headers=H(mgr))
        check("مدير المركز يرى الرواتب", any(t.get("salary") == 75000 for t in r.json()))

        # ---------- 4. الحضور ----------
        recs = {"date": "2026-09-01", "records": [
            {"student_id": student_id, "halaqah_id": halaqah_id, "status": "absent"},
            {"student_id": student2_id, "halaqah_id": halaqah_id, "status": "present"}]}
        r = await c.post("/api/attendance", headers=H(mgr), json=recs)
        check("تسجيل الحضور", r.status_code == 200, r.text[:150])

        recs["records"][0]["status"] = "present"
        await c.post("/api/attendance", headers=H(mgr), json=recs)
        n = await server.db.attendance.count_documents({"student_id": student_id, "date_str": "2026-09-01"})
        row = await server.db.attendance.find_one({"student_id": student_id, "date_str": "2026-09-01"})
        check("[خلل] إعادة الإرسال تصحّح ولا تُكرّر", n == 1 and row["status"] == "present", f"n={n}")
        check("[خلل] سجل الحضور صار يحمل center_id", row.get("center_id") == center_id)

        r = await c.get(f"/api/attendance/halaqah/{halaqah_id}?date=2026-09-01", headers=H(mgr))
        check("[ناقص] GET /attendance/halaqah/{id} صارت موجودة", r.status_code == 200 and len(r.json()) == 2,
              str(r.status_code))

        # إشعار الغياب صار محفوظاً
        notes = await server.db.notifications.count_documents({"type": "absentee_alert"})
        check("[ميزة] تنبيه الغياب يُحفَظ لوليّ الأمر", notes >= 1, f"n={notes}")
        r = await c.get("/api/notifications", headers=H(parent))
        check("وليّ الأمر يقرأ إشعاراته", r.status_code == 200 and r.json()["unread_count"] >= 1, r.text[:150])

        # ---------- 5. لوحة التحكم ----------
        r = await c.get("/api/dashboard/stats", headers=H(mgr))
        stats = r.json()
        check("[خلل] نسبة الحضور لم تعد صفراً دائماً", stats["attendance_rate"] > 0, str(stats))

        await c.post("/api/fees", headers=H(mgr), json={
            "student_id": student_id, "amount": 5000, "due_date": "2026-09-30", "fee_type": "monthly"})
        r = await c.get("/api/dashboard/stats", headers=H(mgr))
        check("[خلل] الرسوم المعلّقة لم تعد صفراً دائماً", r.json()["pending_fees"] == 1, str(r.json()))

        # ---------- 6. الرسوم ----------
        fees = (await c.get("/api/fees", headers=H(mgr))).json()
        fee_id = fees[0]["id"]
        r = await c.post(f"/api/fees/{fee_id}/pay", headers=H(mgr))
        check("تحصيل الرسوم", r.status_code == 200, r.text[:120])
        r = await c.post(f"/api/fees/{fee_id}/pay", headers=H(mgr))
        check("[خلل] التحصيل المكرر مرفوض", r.status_code == 409, str(r.status_code))

        r = await c.get("/api/fees?status=pending", headers=H(mgr))
        check("[خلل] ?status=pending يُصفّي فعلاً", r.json() == [], r.text[:120])

        # ---------- 7. الجدول الأكاديمي ----------
        r = await c.post("/api/academic-schedules", headers=H(admin), json={
            "subject": "تجويد", "day": "الاثنين", "time_slot": "08:00",
            "halaqa_id": halaqah_id, "teacher_id": teacher_id, "center_id": center_id})
        check("[خلل] إنشاء موعد دراسي من مدير بلا مركز لا يُسقط الخادم", r.status_code == 200, r.text[:150])

        # ---------- 8. سلسلة التدقيق ----------
        r = await c.get("/api/audit-logs/verify", headers=H(admin))
        check("[ميزة] سلسلة سجل التدقيق سليمة", r.json().get("intact") is True, r.text[:200])

        one = await server.db.audit_logs.find_one({"action": "collect_fee"})
        await server.db.audit_logs.update_one({"_id": one["_id"]}, {"$set": {"payload.amount": 999999}})
        r = await c.get("/api/audit-logs/verify", headers=H(admin))
        check("[ميزة] التلاعب بسجل مالي يُكتشف",
              r.json().get("intact") is False and r.json()["tampered_entries"], r.text[:200])
        await server.db.audit_logs.update_one({"_id": one["_id"]}, {"$set": {"payload.amount": 5000}})

        # ---------- 9. الملخص المالي والتصدير ----------
        r = await c.get("/api/finance/summary", headers=H(mgr))
        check("[ميزة] الملخص المالي للمركز", r.status_code == 200 and r.json()["revenue"]["fees_collected"] == 5000,
              r.text[:200])
        r = await c.get("/api/finance/summary?center_id=deadbeefdeadbeefdeadbeef", headers=H(mgr))
        check("[أمن] مدير المركز ممنوع من مالية مركز آخر", r.status_code == 403, str(r.status_code))

        r = await c.get("/api/export/students.csv", headers=H(mgr))
        check("[ميزة] تصدير الطلاب CSV", r.status_code == 200 and "الاسم" in r.text, str(r.status_code))
        r = await c.get("/api/export/students.csv", headers=H(teach))
        check("[أمن] المعلم ممنوع من التصدير", r.status_code == 403, str(r.status_code))

        # ---------- 10. الجاهزية والرؤوس ----------
        r = await c.get("/api/health/ready")
        check("[ميزة] فحص الجاهزية يلمس قاعدة البيانات", r.json().get("database") is True, r.text[:120])
        check("[أمن] رؤوس الحماية موجودة",
              r.headers.get("X-Content-Type-Options") == "nosniff" and "X-Request-ID" in r.headers)

        # ---------- 11. قفل الحساب ----------
        for _ in range(11):
            rr = await c.post("/api/auth/login", data={"username": "mgr1", "password": "wrong"},
                              headers={"X-Forwarded-For": f"10.0.0.{_}"})
        check("[أمن] القفل على الحساب يصمد أمام تدوير العناوين", rr.status_code == 429, str(rr.status_code))

        # ---------- 11ب. إبطال المصروف بدل محوه ----------
        r = await c.post("/api/expenses", headers=H(mgr), json={
            "title": "كهرباء", "amount": 30000, "date": "2026-09-01", "center_id": center_id})
        check("إنشاء مصروف", r.status_code == 200, r.text[:120])
        exp_id = r.json()["id"]

        r = await c.get(f"/api/finance/summary?from=2026-09-01&to=2026-09-30", headers=H(mgr))
        before = r.json()["costs"]["expenses"]

        r = await c.delete(f"/api/expenses/{exp_id}?reason=قيد مكرر", headers=H(mgr))
        check("[مبدأ] الحذف صار إبطالاً", r.status_code == 200 and r.json().get("voided") is True, r.text[:150])

        raw = await server.db.expenses.find_one({"_id": server.ObjectId(exp_id)})
        check("[مبدأ] الصفّ المالي باقٍ في السجل", raw is not None)
        check("[مبدأ] الإبطال يسجّل من ومتى ولماذا",
              raw.get("voided") is True and raw.get("voided_by") and raw.get("voided_at")
              and raw.get("void_reason") == "قيد مكرر", str({k: raw.get(k) for k in ("voided","voided_by","void_reason")}))

        r = await c.get(f"/api/finance/summary?from=2026-09-01&to=2026-09-30", headers=H(mgr))
        after = r.json()["costs"]["expenses"]
        check("[مبدأ] المُبطَل خرج من المجموع", after == before - 30000, f"before={before} after={after}")

        r = await c.get("/api/expenses", headers=H(mgr))
        check("[مبدأ] المُبطَل خارج القائمة", all(e["id"] != exp_id for e in r.json()))

        r = await c.delete(f"/api/expenses/{exp_id}?reason=مرة أخرى", headers=H(mgr))
        check("[مبدأ] الإبطال المكرر مرفوض", r.status_code == 409, str(r.status_code))

        # ---------- 12. حذف التسميع (كان زراً وهمياً) ----------
        # الواجهة كانت تنادي PUT /recitations/{id} — نقطة لا وجود لها — وتبتلع الـ404 بصمت
        r = await c.post("/api/recitations", headers=H(mgr), json={
            "student_id": student_id, "teacher_id": teacher_id,
            "surah_name": "البقرة", "start_ayah": 1, "end_ayah": 20,
            "evaluation": "excellent", "mistakes_count": 0, "recitation_type": "new"})
        check("تسجيل تسميع", r.status_code == 200, r.text[:150])
        rec_id = r.json()["id"]

        r = await c.get(f"/api/recitations/student/{student_id}", headers=H(mgr))
        before = len(r.json())

        r = await c.delete(f"/api/recitations/{rec_id}", headers=H(mgr))
        check("[ناقص] DELETE /recitations/{id} صارت موجودة", r.status_code == 200, r.text[:150])

        r = await c.get(f"/api/recitations/student/{student_id}", headers=H(mgr))
        check("[خلل] التسميع المحذوف اختفى فعلاً", len(r.json()) == before - 1,
              f"before={before} after={len(r.json())}")

        # الحذف ناعم: السجل باقٍ للمراجعة، وخارج كل حساب
        raw = await server.db.recitations.find_one({"_id": server.ObjectId(rec_id)})
        check("[خلل] الحذف ناعم لا نهائي", raw is not None and raw.get("is_deleted") is True)

        r = await c.get("/api/recitations", headers=H(mgr))
        check("[خلل] المحذوف خارج القائمة العامة",
              all(x["id"] != rec_id for x in r.json()), r.text[:150])

        r = await c.delete(f"/api/recitations/{rec_id}", headers=H(mgr))
        check("[خلل] الحذف المكرر مرفوض", r.status_code == 409, str(r.status_code))

        # معلّم لا يحذف تسميعاً سجّله غيره
        r = await c.post("/api/recitations", headers=H(mgr), json={
            "student_id": student_id, "teacher_id": teacher_id,
            "surah_name": "النساء", "start_ayah": 1, "end_ayah": 5,
            "evaluation": "good", "mistakes_count": 1, "recitation_type": "new"})
        other_rec = r.json()["id"]
        r = await c.delete(f"/api/recitations/{other_rec}", headers=H(parent))
        check("[أمن] وليّ الأمر ممنوع من حذف التسميع", r.status_code == 403, str(r.status_code))

        # ---------- 12b. دورة التجديد عبر كعكة httpOnly ----------
        rl = await c.post("/api/auth/login", data={"username": "parent1", "password": "Parent1234"})
        tok = rl.json()
        check("[أمن] الدخول لا يُعيد توكن التجديد في الجسم",
              tok.get("refresh_token") is None and bool(tok.get("access_token")), str(list(tok)))

        raw_cookie = " ".join(v for k, v in rl.headers.multi_items() if k.lower() == "set-cookie")
        flat = raw_cookie.lower().replace(" ", "")
        ck = rl.cookies.get("mishkaat_refresh")
        check("[أمن] توكن التجديد وصل في كعكة", bool(ck), raw_cookie[:90])
        check("[أمن] الكعكة httpOnly فلا تقرؤها JavaScript", "httponly" in flat, raw_cookie[:120])
        check("[أمن] الكعكة SameSite=lax تمنع الطلب عبر المواقع", "samesite=lax" in flat, raw_cookie[:120])
        check("[أمن] الكعكة مقصورة على /api/auth", "path=/api/auth" in flat, raw_cookie[:120])

        # الكعكة وحدها تكفي — بلا أي جسم
        r = await c.post("/api/auth/refresh", cookies={"mishkaat_refresh": ck})
        check("[واجهة] التجديد يعمل بالكعكة وحدها",
              r.status_code == 200 and r.json().get("access_token") not in (None, tok["access_token"]),
              r.text[:150])
        new_access = r.json()["access_token"]
        new_ck = r.cookies.get("mishkaat_refresh")
        check("[أمن] التدوير يُصدر كعكة جديدة", bool(new_ck) and new_ck != ck)

        # التدوير: القديم يُبطَل — وهذا سبب وجود single-flight في الواجهة
        r = await c.post("/api/auth/refresh", cookies={"mishkaat_refresh": ck})
        check("[أمن] توكن التجديد القديم يُبطَل بعد التدوير", r.status_code == 401, str(r.status_code))

        r = await c.get("/api/auth/me", headers=H(new_access))
        check("[واجهة] توكن الوصول المجدَّد صالح", r.status_code == 200, str(r.status_code))

        # توكن الوصول لا يصلح للتجديد (فصل الأنواع)
        r = await c.post("/api/auth/refresh", cookies={"mishkaat_refresh": new_access})
        check("[أمن] توكن الوصول لا يُقبل كتوكن تجديد", r.status_code == 401, str(r.status_code))

        # الخروج يُبطل توكن التجديد فعلاً — وإلا بقي صالحاً 7 أيام بعد "الخروج"
        r = await c.post("/api/auth/logout", headers=H(new_access),
                         cookies={"mishkaat_refresh": new_ck})
        check("الخروج ينجح", r.status_code == 200, r.text[:120])
        check("[أمن] الخروج يمسح الكعكة من المتصفّح",
              any("mishkaat_refresh" in v and ('max-age=0' in v.lower().replace(" ", "") or 'expires=' in v.lower())
                  for k, v in r.headers.multi_items() if k.lower() == "set-cookie"),
              " ".join(v for k, v in r.headers.multi_items() if k.lower() == "set-cookie")[:120])
        r = await c.post("/api/auth/refresh", cookies={"mishkaat_refresh": new_ck})
        check("[أمن] الخروج يُبطل توكن التجديد", r.status_code == 401, str(r.status_code))

        # ---------- 13. سباق النقرة المزدوجة على كشف الحضور ----------
        # upsert وحده ليس ذرّياً: بلا الفهرس الفريد يُدرج طلبان متزامنان سجلين
        idx = await server.db.attendance.index_information()
        check("[خلل] الفهرس الفريد للحضور مُنشأ", "uniq_student_day" in idx, str(list(idx)))

        body = {"date": "2026-09-15", "records": [
            {"student_id": student_id, "halaqah_id": halaqah_id, "status": "absent"}]}
        res = await asyncio.gather(
            *[c.post("/api/attendance", headers=H(mgr), json=body) for _ in range(6)],
            return_exceptions=True)
        ok = all(getattr(x, "status_code", 0) == 200 for x in res)
        n = await server.db.attendance.count_documents(
            {"student_id": student_id, "date_str": "2026-09-15"})
        check("[خلل] ستة طلبات متزامنة تُنتج سجلاً واحداً", ok and n == 1,
              f"n={n} codes={[getattr(x,'status_code',type(x).__name__) for x in res]}")

        body["records"][0]["status"] = "present"
        await c.post("/api/attendance", headers=H(mgr), json=body)
        row = await server.db.attendance.find_one(
            {"student_id": student_id, "date_str": "2026-09-15"})
        check("[خلل] التصحيح بعد السباق ما زال يعمل", row["status"] == "present", str(row.get("status")))

    await server.client.drop_database(DB)

    # تنظيف أغلفة gzip الخاصة بـ GZipMiddleware قبل إغلاق حلقة الأحداث.
    # بدونه يُنهيها المفسّر بعد إغلاق الحلقة فيطبع عشرات أسطر
    # "Exception ignored ... I/O operation on closed file" التي تُغرق النتيجة وتُخفي أي فشل.
    gc.collect()

    print("\n" + "=" * 62)
    print(f"  نجح: {len(PASSED)}   فشل: {len(FAILED)}")
    if FAILED:
        print("  الفاشل: " + " | ".join(FAILED))
    print("=" * 62)
    return 1 if FAILED else 0


sys.exit(asyncio.run(main()))
