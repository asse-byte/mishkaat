import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "quran_center")

async def run_migrations():
    print(f"Connecting to MongoDB at {MONGO_URL}...")
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("Creating compound indexes (background=True)...")
    
    # 1. users
    await db.users.create_index([("center_id", 1), ("role", 1)], background=True)
    await db.users.create_index("username", unique=True, background=True)
    
    # 2. students
    await db.students.create_index("center_id", background=True)
    await db.students.create_index("halaqah_id", background=True)
    await db.students.create_index("phone", background=True)
    
    # 3. teachers
    await db.teachers.create_index("center_id", background=True)
    await db.teachers.create_index("user_id", background=True)
    
    # 4. attendance
    await db.attendance.create_index([("center_id", 1), ("date", 1)], background=True)
    await db.attendance.create_index([("student_id", 1), ("date", 1)], background=True)
    
    # 5. recitations (memorization_records)
    await db.recitations.create_index([("center_id", 1), ("student_id", 1)], background=True)
    await db.recitations.create_index("date", background=True)
    
    # 6. finances (fees, salaries, expenses)
    await db.fees.create_index([("center_id", 1), ("status", 1), ("due_date", 1)], background=True)
    await db.salaries.create_index([("center_id", 1), ("month", 1)], background=True)
    await db.expenses.create_index([("center_id", 1), ("category", 1), ("date", 1)], background=True)
    
    # 7. audit_logs
    await db.audit_logs.create_index([("center_id", 1), ("timestamp", 1)], background=True)
    await db.audit_logs.create_index("timestamp", background=True)
    
    # 8. notifications
    await db.notifications.create_index([("user_id", 1), ("is_read", 1)], background=True)
    
    # 9. academic_schedules (v2.1 specification)
    await db.academic_schedules.create_index([("center_id", 1), ("day", 1), ("time_slot", 1)], background=True)
    # 10. teacher_evaluations
    await db.teacher_evaluations.create_index([("center_id", 1), ("teacher_id", 1)], background=True)
    # 11. competitions & contestants
    await db.competitions.create_index("center_id", background=True)
    await db.competition_contestants.create_index([("competition_id", 1), ("student_id", 1)], background=True)
    # 12. bulk_messages
    await db.bulk_messages.create_index([("center_id", 1), ("sender_id", 1)], background=True)
    
    print("Creating TTL Indexes...")
    # Delete notifications after 90 days
    try:
        await db.notifications.drop_index("created_at_1")
    except Exception:
        pass
    try:
        await db.notifications.create_index("created_at", expireAfterSeconds=7776000, background=True)
    except Exception as e:
        print(f"Warning: Notifications TTL index failed: {e}")
    
    # Delete non-financial audit logs after 2 years using purge_at field
    try:
        await db.audit_logs.drop_index("purge_at_1")
    except Exception:
        pass
    try:
        await db.audit_logs.create_index("purge_at", expireAfterSeconds=0, background=True)
    except Exception as e:
        print(f"Warning: Audit logs TTL index failed: {e}")
    
    # Delete password resets after 10 minutes
    try:
        await db.password_resets.drop_index("created_at_1")
    except Exception:
        pass
    try:
        await db.password_resets.create_index("created_at", expireAfterSeconds=600, background=True)
    except Exception as e:
        print(f"Warning: Password resets TTL index failed: {e}")
    
    print("SUCCESS: High-performance production indexes created successfully!")
    client.close()

if __name__ == "__main__":
    asyncio.run(run_migrations())
