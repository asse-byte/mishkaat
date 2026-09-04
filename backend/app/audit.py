"""سلسلة سجل التدقيق."""

from datetime import datetime
from datetime import timedelta
from pymongo import ReturnDocument
import asyncio
import hashlib
import json

from app.config import AUDIT_PERMANENT_ACTIONS, logger
from app.db import db


async def _next_audit_seq() -> int:
    """رقم تسلسلي ذرّي لسلسلة سجل التدقيق"""
    doc = await db.counters.find_one_and_update(
        {"_id": "audit_logs"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["seq"])

async def _previous_log_hash(seq: int) -> tuple[str, bool]:
    """
    بصمة السجل السابق حسب الترتيب الذرّي. يعيد (البصمة، هل هناك انقطاع في السلسلة).
    """
    if seq <= 1:
        return "0" * 64, False
    # قد يكون السجل السابق قيد الكتابة الآن من عامل آخر — ننتظره لحظات
    for _ in range(50):
        prev = await db.audit_logs.find_one({"seq": seq - 1}, {"log_hash": 1})
        if prev:
            return prev.get("log_hash", "0" * 64), False
        await asyncio.sleep(0.02)
    logger.error(f"audit chain: previous entry seq={seq - 1} never appeared; recording a marked gap")
    return "0" * 64, True

async def write_audit_log(actor_id: str, center_id: str, action: str, payload: dict, client_ip: str = None) -> dict:
    """
    إضافة سجل تدقيق مالي/إداري غير قابل للتلاعب (سلسلة تشفير SHA-256).

    [AUDIT-2026-09-03 fix] كان السجل السابق يُقرأ بـ sort على الوقت: عند كتابتين متزامنتين يحصل
    السجلّان على نفس previous_hash فتنشقّ السلسلة بصمت وتفشل أي مراجعة لاحقة دون سبب ظاهر.
    صار لكل سجل رقم تسلسلي ذرّي (counters) والسلسلة تُبنى عليه، ويُعلَّم أي انقطاع صراحةً
    بحقل chain_gap بدل التظاهر بأن السلسلة سليمة.
    """
    # MongoDB يخزّن التاريخ بدقة الملي ثانية فقط. لو بُصمت الطوابع بدقة الميكرو ثانية لاختلفت
    # البصمة المُعاد حسابها عن المخزَّنة في كل سجل، فيبلّغ التحقق عن "تلاعب" في سجل سليم.
    now_raw = datetime.utcnow()
    timestamp = now_raw.replace(microsecond=(now_raw.microsecond // 1000) * 1000)
    try:
        seq = await _next_audit_seq()
        previous_hash, gap = await _previous_log_hash(seq)
    except Exception as e:
        logger.error(f"audit chain sequencing failed: {e}")
        seq, previous_hash, gap = None, "0" * 64, True

    serialized_payload = json.dumps(payload, sort_keys=True, default=str)

    hash_input = f"{seq}:{actor_id}:{center_id}:{action}:{serialized_payload}:{timestamp.isoformat()}:{previous_hash}"
    log_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    log_entry = {
        "seq": seq,
        "actor_id": actor_id,
        "center_id": center_id,
        "action": action,
        "payload": payload,
        "timestamp": timestamp,
        "client_ip": client_ip or "system",
        "previous_hash": previous_hash,
        "log_hash": log_hash,
    }
    if gap:
        log_entry["chain_gap"] = True

    if action not in AUDIT_PERMANENT_ACTIONS:
        log_entry["purge_at"] = timestamp + timedelta(days=730)

    try:
        await db.audit_logs.insert_one(log_entry)
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")

    return log_entry

def audit_hash_input(entry: dict) -> str:
    """إعادة بناء نص البصمة كما كُتب — تستخدمه نقطة التحقق من سلامة السلسلة"""
    ts = entry.get("timestamp")
    ts_iso = ts.isoformat() if isinstance(ts, datetime) else str(ts)
    payload = json.dumps(entry.get("payload", {}), sort_keys=True, default=str)
    return (
        f"{entry.get('seq')}:{entry.get('actor_id')}:{entry.get('center_id')}:"
        f"{entry.get('action')}:{payload}:{ts_iso}:{entry.get('previous_hash')}"
    )
