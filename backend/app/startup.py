"""تهيئة الفهارس والحسابات الأولى."""

from app.clock import utcnow

from pymongo.errors import OperationFailure

from bson import ObjectId
import os
import secrets

from app.config import IS_PRODUCTION, LOCKOUT_MINUTES, REGISTER_WINDOW_MINUTES, logger
from app.db import db
from app.security import get_password_hash


# ==================== Startup Events ====================

async def startup_event():
    """Initialize database with default data and create indexes"""
    
    async def _safe_create_index(coll, *args, **kwargs):
        try:
            await coll.create_index(*args, **kwargs)
        except OperationFailure as e:
            if e.code == 85:  # IndexOptionsConflict
                try:
                    info = await coll.index_information()
                    keys = args[0]
                    target_key = [(keys, 1)] if isinstance(keys, str) else list(keys)
                    for idx_name, idx_spec in info.items():
                        if idx_spec.get("key") == target_key:
                            await coll.drop_index(idx_name)
                            break
                    await coll.create_index(*args, **kwargs)
                except Exception as exc:
                    logger.warning(f"Could not recreate index on {coll.name}: {exc}")
            else:
                raise

    # Create Indexes for performance
    await _safe_create_index(db.users, "username", unique=True)
    await db.users.create_index("role")
    await db.users.create_index("center_id")
    await db.students.create_index("center_id")
    await db.students.create_index("halaqah_id")
    await db.teachers.create_index("center_id")
    await db.audit_logs.create_index("timestamp")
    
    # [AUDIT-2026-05-22 performance: add critical query optimization indexes]
    await db.recitations.create_index("student_id")
    await db.recitations.create_index([("student_id", 1), ("date", -1)])
    await db.recitations.create_index("teacher_id")
    await db.attendance.create_index("student_id")
    await db.attendance.create_index([("student_id", 1), ("date", -1)])
    await db.attendance.create_index("halaqah_id")
    await db.attendance.create_index([("halaqah_id", 1), ("date_str", 1)])

    # [إصلاح 2026-09-03] الفهرس الفريد هو ما يجعل منع الازدواج حقيقياً.
    # upsert وحده ليس ذرّياً بلا فهرس فريد: طلبان متزامنان (نقرة مزدوجة على «حفظ») لا يجد
    # أيّهما سجلاً فيُدرجان معاً — وهو الازدواج نفسه الذي جاء الإصلاح لمنعه.
    # لا نُفشل الإقلاع إن كانت هناك تكرارات قديمة: تنشيط الفهرس حينها يوقف الخدمة كلها،
    # فنُسجّل تحذيراً واضحاً ويبقى الاستبدال عاملاً، ويُنشَأ الفهرس بعد تنظيف التكرارات.
    try:
        await db.attendance.create_index(
            [("student_id", 1), ("date_str", 1)], unique=True, name="uniq_student_day"
        )
    except Exception as exc:
        logger.warning(
            "تعذّر إنشاء الفهرس الفريد للحضور (student_id + date_str): %s — "
            "الأرجح وجود سجلات مكرّرة قديمة. نظّفها ثم أعد التشغيل ليصبح منع الازدواج مضموناً.",
            exc,
        )
    await db.fees.create_index("student_id")
    await db.fees.create_index("status")
    await db.expenses.create_index([("center_id", 1), ("created_at", -1)])
    await db.halaqat.create_index("center_id")
    await db.halaqat.create_index("teacher_id")
    await db.salaries.create_index([("center_id", 1), ("created_at", -1)])
    await db.salaries.create_index("teacher_id")
    await db.review_plans.create_index([("center_id", 1), ("created_at", -1)])
    await db.review_plans.create_index("teacher_id")

    # [AUDIT-2026-05-22 fix: indexes that support parent/student ownership lookups in check_student_access]
    await db.students.create_index("parent_phone")
    await db.students.create_index("phone")
    await db.students.create_index("user_id")
    await db.teachers.create_index("user_id")
    await db.users.create_index("phone")
    await db.centers.create_index("manager_id")

    # [AUDIT-2026-05-22 fix: TTL indexes for token revocation list and rate-limit storage]
    await _safe_create_index(db.revoked_tokens, "jti", unique=True)
    await _safe_create_index(db.revoked_tokens, "expires_at", expireAfterSeconds=0)
    await _safe_create_index(
        db.login_attempts, "last_seen", expireAfterSeconds=max(LOCKOUT_MINUTES * 60 * 2, 3600)
    )
    await _safe_create_index(
        db.register_attempts, "last_seen", expireAfterSeconds=REGISTER_WINDOW_MINUTES * 60 * 2
    )

    # [AUDIT-2026-09-03 additions: فهارس الإصلاحات الجديدة]
    # نافذة طلبات إعادة التعيين تُنظَّف تلقائياً
    await _safe_create_index(db.reset_requests, "last_seen", expireAfterSeconds=7200)
    # رموز إعادة التعيين المنتهية تُحذف من نفسها بدل أن تتراكم
    await _safe_create_index(db.password_resets, "expires_at", expireAfterSeconds=0)
    await _safe_create_index(db.password_resets, "username", unique=True)
    # سلسلة سجل التدقيق: ترتيب ذرّي فريد (جزئي، لأن السجلات القديمة بلا seq)
    await _safe_create_index(
        db.audit_logs, "seq", unique=True, partialFilterExpression={"seq": {"$exists": True, "$type": "number"}}
    )
    await _safe_create_index(db.audit_logs, [("center_id", 1), ("timestamp", -1)])
    await _safe_create_index(db.audit_logs, "action")
    # النطاق الجديد لسجلات الحضور والرسوم (كانا بلا center_id — انظر /api/dashboard/stats)
    await _safe_create_index(db.attendance, [("student_id", 1), ("date_str", 1)])
    await _safe_create_index(db.attendance, [("center_id", 1), ("date", -1)])
    await _safe_create_index(db.fees, [("center_id", 1), ("status", 1)])
    await _safe_create_index(db.fees, [("student_id", 1), ("status", 1)])
    await _safe_create_index(db.students, [("center_id", 1), ("is_active", 1)])
    await _safe_create_index(db.salaries, [("center_id", 1), ("month", 1)])
    # [إضافة 2026-09-05 — طبقة التحفيز، FR12/FR13 في تقرير Halaqtna]
    # المفتاح الفريد على (الطالب، السبب، المصدر) هو ما يجعل منح النقاط عديم
    # الأثر عند التكرار: إعادةُ إرسال كشف الحضور أو إعادة معالجة تسميعة لا
    # تمنح النقاط مرّتين. بدونه يستطيع أيّ تكرار أن يضخّم رصيد طالب بلا حدّ.
    await _safe_create_index(
        db.xp_ledger, [("student_id", 1), ("reason", 1), ("source_id", 1)], unique=True
    )
    await _safe_create_index(db.xp_ledger, [("student_id", 1), ("created_at", -1)])
    await _safe_create_index(db.xp_ledger, [("center_id", 1), ("created_at", -1)])
    # الوسام يُنال مرّة واحدة لكل طالب
    await _safe_create_index(
        db.student_badges, [("student_id", 1), ("badge_code", 1)], unique=True
    )
    await _safe_create_index(db.student_badges, [("center_id", 1), ("earned_at", -1)])

    # الإشعارات المخزَّنة: قراءة سريعة للمستخدم، وتنظيف تلقائي بعد 180 يوماً
    await _safe_create_index(db.notifications, [("user_id", 1), ("created_at", -1)])
    await _safe_create_index(db.notifications, [("user_id", 1), ("read", 1)])
    await _safe_create_index(db.notifications, "created_at", expireAfterSeconds=180 * 24 * 3600)

    # [إصلاح 2026-09-04] تذاكر فتح قناة البثّ: عمرها دقيقة وMongo يحذف المنتهية بنفسه
    await _safe_create_index(db.stream_tickets, "ticket", unique=True)
    await _safe_create_index(db.stream_tickets, "created_at", expireAfterSeconds=300)
    # قناة البثّ تستطلع الإشعارات تصاعدياً حسب وقت الإنشاء
    await _safe_create_index(db.notifications, [("user_id", 1), ("created_at", 1)])

    # Compound and performance indexes for new SaaS collections (v2.1 specification)
    await db.academic_schedules.create_index([("center_id", 1), ("day", 1), ("time_slot", 1)])
    await db.teacher_evaluations.create_index([("center_id", 1), ("teacher_id", 1)])
    await db.competitions.create_index("center_id")
    await db.competition_contestants.create_index([("competition_id", 1), ("student_id", 1)])
    await db.bulk_messages.create_index([("center_id", 1), ("sender_id", 1)])

    # الشهادات: المنعُ من التكرار في القاعدة لا في الكود وحده. فحصٌ في الكود
    # يسبق كتابةً ينجح مرّتين حين يُضغط الزرّ مرّتين في اللحظة نفسها.
    await _safe_create_index(
        db.certificates, [("student_id", 1), ("milestone", 1)], unique=True,
        partialFilterExpression={"kind": "milestone"}, name="uniq_student_milestone")
    await _safe_create_index(
        db.certificates, [("competition_id", 1), ("student_id", 1)], unique=True,
        partialFilterExpression={"kind": "competition"}, name="uniq_competition_student")
    await _safe_create_index(db.certificates, [("center_id", 1), ("issued_at", -1)])
    await _safe_create_index(db.certificates, [("serial", 1)], unique=True)

    # [AUDIT-2026-05-22 fix: admin bootstrap — never ship default password to production]
    SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "false").lower() in ("true", "1", "yes")
    INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD")

    existing_admin = await db.users.find_one({"username": "admin"})
    if not existing_admin:
        if INITIAL_ADMIN_PASSWORD:
            admin_password = INITIAL_ADMIN_PASSWORD
            password_source = "INITIAL_ADMIN_PASSWORD env"
        elif IS_PRODUCTION:
            raise RuntimeError(
                "SECURITY: INITIAL_ADMIN_PASSWORD must be set when bootstrapping a production instance"
            )
        else:
            admin_password = secrets.token_urlsafe(16)
            password_source = "RANDOM (printed once below)"
            print("=" * 60)
            print("[KEY] GENERATED admin password (save now, will not be shown again):")
            print(f"   {admin_password}")
            print("=" * 60)
        await db.users.insert_one({
            "username": "admin",
            "name": "مدير النظام",
            "email": os.getenv("ADMIN_EMAIL", "admin@quran-center.com"),
            "role": "admin",
            "hashed_password": get_password_hash(admin_password),
            "is_active": True,
            "user_version": 0,
            "created_at": utcnow(),
        })
        print(f"[SUCCESS] Admin user provisioned (password source: {password_source})")

    # [AUDIT-2026-09-03 fix — كلمة مرور ثابتة لأقوى حساب في النظام]
    # كان الحساب الأعلى صلاحية (super_admin: يرى كل المراكز ويعطّلها) يُنشأ بكلمة المرور
    # "superadmin123" كلما لم يكن INITIAL_ADMIN_PASSWORD مضبوطاً — بما في ذلك الإنتاج، لأن
    # الحماية السابقة تفحص حساب admin فقط، فإذا كان admin موجوداً من قبل مرّ هذا السطر بلا اعتراض.
    # كذلك كان يشارك admin نفس كلمة المرور، فكسر أحدهما يكسر الآخر.
    existing_super_admin = await db.users.find_one({"username": "superadmin"})
    if not existing_super_admin:
        super_admin_pass = os.getenv("INITIAL_SUPER_ADMIN_PASSWORD")
        if not super_admin_pass:
            if IS_PRODUCTION:
                raise RuntimeError(
                    "SECURITY: INITIAL_SUPER_ADMIN_PASSWORD must be set when bootstrapping the super admin"
                )
            super_admin_pass = secrets.token_urlsafe(16)
            print("=" * 60)
            print("[KEY] GENERATED superadmin password (save now, will not be shown again):")
            print(f"   {super_admin_pass}")
            print("=" * 60)
        await db.users.insert_one({
            "username": "superadmin",
            "name": "المدير العام (الوزارة/الجمعية)",
            "email": "superadmin@quran-center.com",
            "role": "super_admin",
            "hashed_password": get_password_hash(super_admin_pass),
            "is_active": True,
            "user_version": 0,
            "created_at": utcnow(),
        })
        print("[SUCCESS] Super Admin user provisioned")

    if not SEED_DEMO_DATA:
        print("[INFO] SEED_DEMO_DATA is false — skipping demo users/centers/halaqat/students seeding")
        return

    # [AUDIT-2026-05-22 fix: demo accounts now opt-in only]
    default_users = [
        {
            "username": "manager1",
            "name": "أحمد محمد - مدير المركز",
            "email": "manager@quran-center.com",
            "role": "center_manager",
            "center_id": "center_1",
            "hashed_password": get_password_hash("manager123"),
            "is_active": True,
            "user_version": 0,
            "created_at": utcnow()
        },
        {
            "username": "teacher1",
            "name": "الشيخ محمد علي",
            "email": "teacher@quran-center.com",
            "role": "teacher",
            "center_id": "center_1",
            "hashed_password": get_password_hash("teacher123"),
            "is_active": True,
            "user_version": 0,
            "created_at": utcnow()
        },
        {
            "username": "student1",
            "name": "أحمد الطالب",
            "email": "student@quran-center.com",
            "role": "student",
            "center_id": "center_1",
            "hashed_password": get_password_hash("student123"),
            "is_active": True,
            "user_version": 0,
            "created_at": utcnow()
        },
        {
            "username": "parent1",
            "name": "أبو أحمد",
            "email": "parent@quran-center.com",
            "role": "parent",
            "hashed_password": get_password_hash("parent123"),
            "is_active": True,
            "user_version": 0,
            "created_at": utcnow()
        }
    ]
    for u in default_users:
        await db.users.update_one(
            {"username": u["username"]},
            {"$setOnInsert": u},
            upsert=True
        )
    print("[SUCCESS] Demo users ensured (SEED_DEMO_DATA=true)")

    # Seed centers if none exist
    centers_count = await db.centers.count_documents({})
    if centers_count == 0:
        # Get manager user id
        manager_user = await db.users.find_one({"username": "manager1"})
        manager_id = str(manager_user["_id"]) if manager_user else None
        
        default_centers = [
            {
                "name": "مركز النور للقرآن الكريم",
                "address": "باماكو - حي النيجر",
                "phone": "+223 70 00 00 01",
                "manager_id": manager_id,
                "manager_name": "أحمد محمد - مدير المركز",
                "is_active": True,
                "created_at": utcnow()
            },
            {
                "name": "مركز الفجر للتحفيظ",
                "address": "سيغو - وسط المدينة",
                "phone": "+223 70 00 00 02",
                "manager_id": None,
                "manager_name": "عمر خالد سعيد",
                "is_active": True,
                "created_at": utcnow()
            },
            {
                "name": "مركز الهدى القرآني",
                "address": "موبتي - حي السوق",
                "phone": "+223 70 00 00 03",
                "manager_id": None,
                "manager_name": "محمد سعيد أحمد",
                "is_active": True,
                "created_at": utcnow()
            },
        ]
        result = await db.centers.insert_many(default_centers)
        center_ids = [str(id) for id in result.inserted_ids]
        
        # Update manager's center_id
        if manager_id and center_ids:
            await db.users.update_one(
                {"username": "manager1"},
                {"$set": {"center_id": center_ids[0]}}
            )
            await db.users.update_one(
                {"username": "teacher1"},
                {"$set": {"center_id": center_ids[0]}}
            )
            await db.users.update_one(
                {"username": "student1"},
                {"$set": {"center_id": center_ids[0]}}
            )
        
        print(f"[SUCCESS] Default centers created: {center_ids}")
        
        # Seed teachers
        default_teachers = [
            {
                "name": "الشيخ محمد علي أحمد",
                "phone": "+223 70 11 22 33",
                "center_id": center_ids[0],
                "specialization": "حفص عن عاصم",
                "is_active": True,
                "hire_date": utcnow()
            },
            {
                "name": "الشيخ عبدالله محمود",
                "phone": "+223 70 22 33 44",
                "center_id": center_ids[0],
                "specialization": "ورش عن نافع",
                "is_active": True,
                "hire_date": utcnow()
            },
            {
                "name": "الشيخ إبراهيم سعيد",
                "phone": "+223 70 33 44 55",
                "center_id": center_ids[0],
                "specialization": "حفص عن عاصم",
                "is_active": True,
                "hire_date": utcnow()
            },
        ]
        teacher_result = await db.teachers.insert_many(default_teachers)
        teacher_ids = [str(id) for id in teacher_result.inserted_ids]
        print(f"[SUCCESS] Default teachers created: {teacher_ids}")

        # [إصلاح 2026-09-06] البذرة كانت تُنشئ حساب teacher1 وسجلات المحفّظين
        # ولا تربط بينها إطلاقاً (user_id = None في كلّها). ومنذ صار نطاق المحفّظ
        # حلقاتِه — يُستدلّ عليها من users → teachers.user_id → halaqat.teacher_id —
        # فإن حسابَ محفّظ بلا سجلّ مرتبط لا يرى شيئاً على الإطلاق. الربط هنا.
        teacher_user = await db.users.find_one({"username": "teacher1"})
        if teacher_user and teacher_ids:
            await db.teachers.update_one(
                {"_id": teacher_result.inserted_ids[0]},
                {"$set": {"user_id": str(teacher_user["_id"])}},
            )
            print("[SUCCESS] teacher1 linked to the first demo teacher record")
        
        # Seed halaqat
        default_halaqat = [
            {
                "name": "حلقة الفجر",
                "teacher_id": teacher_ids[0],
                "teacher_name": "الشيخ محمد علي أحمد",
                "center_id": center_ids[0],
                "schedule": "يومياً بعد صلاة الفجر",
                "time": "06:00 - 07:30",
                "location": "القاعة الرئيسية",
                "max_students": 25,
                "current_students": 0,
                "is_active": True,
            },
            {
                "name": "حلقة الضحى",
                "teacher_id": teacher_ids[1],
                "teacher_name": "الشيخ عبدالله محمود",
                "center_id": center_ids[0],
                "schedule": "يومياً ماعدا الجمعة",
                "time": "09:00 - 10:30",
                "location": "القاعة الثانية",
                "max_students": 20,
                "current_students": 0,
                "is_active": True,
            },
            {
                "name": "حلقة العصر",
                "teacher_id": teacher_ids[0],
                "teacher_name": "الشيخ محمد علي أحمد",
                "center_id": center_ids[0],
                "schedule": "يومياً بعد صلاة العصر",
                "time": "16:30 - 18:00",
                "location": "القاعة الرئيسية",
                "max_students": 20,
                "current_students": 0,
                "is_active": True,
            },
            {
                "name": "حلقة المغرب",
                "teacher_id": teacher_ids[2],
                "teacher_name": "الشيخ إبراهيم سعيد",
                "center_id": center_ids[0],
                "schedule": "يومياً بعد صلاة المغرب",
                "time": "19:00 - 20:30",
                "location": "القاعة الثانية",
                "max_students": 20,
                "current_students": 0,
                "is_active": True,
            },
            {
                "name": "حلقة المراجعة",
                "teacher_id": teacher_ids[1],
                "teacher_name": "الشيخ عبدالله محمود",
                "center_id": center_ids[0],
                "schedule": "يومياً بعد صلاة الظهر",
                "time": "13:00 - 14:30",
                "location": "القاعة الثالثة",
                "max_students": 15,
                "current_students": 0,
                "is_active": True,
            },
        ]
        halaqah_result = await db.halaqat.insert_many(default_halaqat)
        halaqah_ids = [str(id) for id in halaqah_result.inserted_ids]
        print(f"[SUCCESS] Default halaqat created: {halaqah_ids}")
        
        # Seed students
        default_students = [
            {
                "name": "أحمد محمد علي",
                "phone": "+223 70 11 22 33",
                "parent_name": "محمد علي",
                "parent_phone": "+223 70 44 55 66",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[0],
                "halaqah_name": "حلقة الفجر",
                "memorization_plan": "plan_3_years",
                "student_type": "memorizing",
                "is_active": True,
                "enrollment_date": utcnow(),
                "progress": 17,
                "current_surah": "البقرة",
                "current_ayah": 150,
            },
            {
                "name": "عمر خالد سعيد",
                "phone": "+223 70 22 33 44",
                "parent_name": "خالد سعيد",
                "parent_phone": "+223 70 55 66 77",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[0],
                "halaqah_name": "حلقة الفجر",
                "memorization_plan": "plan_4_years",
                "student_type": "memorizing",
                "is_active": True,
                "enrollment_date": utcnow(),
                "progress": 12,
                "current_surah": "آل عمران",
                "current_ayah": 50,
            },
            {
                "name": "سعيد محمود أحمد",
                "phone": "+223 70 33 44 55",
                "parent_name": "محمود أحمد",
                "parent_phone": "+223 70 66 77 88",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[4],
                "halaqah_name": "حلقة المراجعة",
                "memorization_plan": "plan_review",
                "student_type": "reviewing",
                "is_active": True,
                "enrollment_date": utcnow(),
                "progress": 100,
                "current_surah": "الفاتحة",
                "current_ayah": 1,
            },
            {
                "name": "إبراهيم موسى عمر",
                "phone": "+223 70 44 55 66",
                "parent_name": "موسى عمر",
                "parent_phone": "+223 70 77 88 99",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[1],
                "halaqah_name": "حلقة الضحى",
                "memorization_plan": "plan_2_years",
                "student_type": "memorizing",
                "is_active": True,
                "enrollment_date": utcnow(),
                "progress": 25,
                "current_surah": "النساء",
                "current_ayah": 80,
            },
            {
                "name": "خالد أحمد علي",
                "phone": "+223 70 55 66 77",
                "parent_name": "أحمد علي",
                "parent_phone": "+223 70 88 99 00",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[2],
                "halaqah_name": "حلقة العصر",
                "memorization_plan": "plan_5_years",
                "student_type": "memorizing",
                "is_active": True,
                "enrollment_date": utcnow(),
                "progress": 8,
                "current_surah": "البقرة",
                "current_ayah": 50,
            },
        ]
        await db.students.insert_many(default_students)
        
        # Update halaqat student counts
        for i, halaqah_id in enumerate(halaqah_ids):
            count = await db.students.count_documents({"halaqah_id": halaqah_id, "is_active": True})
            await db.halaqat.update_one(
                {"_id": ObjectId(halaqah_id)},
                {"$set": {"current_students": count}}
            )
        
        # [إصلاح 2026-09-04] حساب وليّ الأمر التجريبي لم يكن يحمل رقم هاتف، والربط
        # بالأبناء يقوم على تطابق parent_phone — فكان parent1 لا يرى طالباً ولا يصله
        # تنبيه غياب أبداً، وتبدو الميزة معطّلة في أي عرض للنظام. نربطه بأول طالب.
        first_student = await db.students.find_one({"center_id": center_ids[0]})
        if first_student and first_student.get("parent_phone"):
            await db.users.update_one(
                {"username": "parent1"},
                {"$set": {"phone": first_student["parent_phone"], "center_id": center_ids[0]}},
            )
            # لا تُطبَع أسماء عربية هنا: طرفية ويندوز الافتراضية cp1252 لا تُرمّزها،
            # فيرفع print استثناء UnicodeEncodeError داخل دورة الحياة ويسقط الإقلاع كلّه.
            # بقية الملف تلتزم ASCII في الطباعة للسبب نفسه.
            print("[SUCCESS] parent1 linked to the first demo student")

        print("[SUCCESS] Default students created")
