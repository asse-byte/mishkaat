"""الرسائل الجماعية."""

from app.clock import utcnow

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from typing import List

from app.common import safe_object_id, serialize_doc
from app.db import db
from app.models import BulkMessageCreate, BulkMessageResponse, ReplyPayload
from app.security import get_current_user

router = APIRouter()


@router.post("/api/messages/broadcast", response_model=BulkMessageResponse)
async def create_broadcast_message(msg: BulkMessageCreate, current_user: dict = Depends(get_current_user)):
    """إرسال رسالة جماعية (بث) جديدة للمعلمين أو مدراء المراكز"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    center_id = current_user.get("center_id")
    if not center_id:
        if current_user["role"] == "super_admin":
            center_id = "global"
        else:
            raise HTTPException(status_code=400, detail="يجب ربط حسابك بمركز معتمد")
        
    msg_dict = msg.model_dump()
    msg_dict["center_id"] = center_id
    msg_dict["sender_id"] = str(current_user["_id"])
    msg_dict["sender_name"] = current_user.get("name") or current_user.get("username")
    msg_dict["sent_at"] = utcnow()
    msg_dict["replies"] = []
    
    result = await db.bulk_messages.insert_one(msg_dict)
    
    return {
        **msg_dict,
        "id": str(result.inserted_id)
    }

@router.get("/api/messages/inbox", response_model=List[BulkMessageResponse])
async def get_received_broadcasts(current_user: dict = Depends(get_current_user)):
    """عرض الرسائل الجماعية الواردة للمعلم أو مدير المركز"""
    role = current_user["role"]
    center_id = current_user.get("center_id")
    
    if role == "center_manager":
        # مدير المركز يستقبل الرسائل المرسلة له من الإشراف العام (Super Admin)
        query = {
            "$or": [
                {"center_id": center_id, "recipient_role": "center_manager"},
                {"center_id": "global", "recipient_role": "center_manager"}
            ]
        }
    else:
        if not center_id:
            return []
        query = {"center_id": center_id}
        if role == "teacher":
            query["recipient_role"] = "all_teachers"
        else:
            query["recipient_role"] = role
        
    messages = await db.bulk_messages.find(query).sort("sent_at", -1).to_list(100)
    return [serialize_doc(m) for m in messages]

@router.post("/api/messages/{message_id}/reply", response_model=BulkMessageResponse)
async def reply_to_broadcast(
    message_id: str,
    payload: ReplyPayload,
    current_user: dict = Depends(get_current_user)
):
    """الرد على رسالة جماعية واردة"""
    if current_user["role"] not in ["teacher", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح - للرد يجب أن تكون معلماً أو مديراً")
        
    msg_obj_id = safe_object_id(message_id)
    message = await db.bulk_messages.find_one({"_id": msg_obj_id})
    if not message:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
    if message.get("center_id") != "global" and message.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    reply = {
        "teacher_id": str(current_user["_id"]),
        "teacher_name": current_user.get("name") or current_user.get("username") or "مدير مركز",
        "content": payload.content,
        "timestamp": utcnow()
    }
    
    await db.bulk_messages.update_one(
        {"_id": msg_obj_id},
        {"$push": {"replies": reply}}
    )
    
    updated = await db.bulk_messages.find_one({"_id": msg_obj_id})
    return serialize_doc(updated)

@router.get("/api/messages/broadcasts", response_model=List[BulkMessageResponse])
async def get_sent_broadcasts(current_user: dict = Depends(get_current_user)):
    """عرض رسائل البث المرسلة من قبل المدير مع الردود الواردة"""
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    if role == "super_admin":
        query = {"center_id": "global"}
    else:
        center_id = current_user.get("center_id")
        if not center_id:
            return []
        query = {"center_id": center_id}
        if role == "center_manager":
            query["sender_id"] = str(current_user["_id"])
        
    messages = await db.bulk_messages.find(query).sort("sent_at", -1).to_list(100)
    return [serialize_doc(m) for m in messages]
