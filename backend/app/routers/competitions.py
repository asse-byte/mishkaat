"""المسابقات القرآنية."""

from datetime import datetime
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from typing import List

from app.common import safe_object_id, serialize_doc
from app.db import db
from app.models import CompetitionContestantCreate, CompetitionContestantResponse, CompetitionCreate, CompetitionResponse, ContestantGrades
from app.security import get_current_user

router = APIRouter()


# ==================== Quran Competitions Routes ====================

@router.post("/api/competitions", response_model=CompetitionResponse)
async def create_competition(comp: CompetitionCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء مسابقة قرآنية سنوية جديدة"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    center_id = current_user.get("center_id")
    if not center_id:
        raise HTTPException(status_code=400, detail="يجب ربط حسابك بمركز تحفيظ معتمد")
        
    comp_dict = comp.model_dump()
    comp_dict["center_id"] = center_id
    comp_dict["created_at"] = datetime.utcnow()
    
    result = await db.competitions.insert_one(comp_dict)
    
    return {
        **comp_dict,
        "id": str(result.inserted_id)
    }

@router.get("/api/competitions", response_model=List[CompetitionResponse])
async def get_competitions(current_user: dict = Depends(get_current_user)):
    """عرض قائمة المسابقات القرآنية في المركز"""
    role = current_user["role"]
    query = {}
    if role != "super_admin":
        center_id = current_user.get("center_id")
        if not center_id:
            return []
        query["center_id"] = center_id
        
    comps = await db.competitions.find(query).sort("created_at", -1).to_list(100)
    return [serialize_doc(c) for c in comps]

@router.post("/api/competitions/{comp_id}/register", response_model=CompetitionContestantResponse)
async def register_contestant(
    comp_id: str,
    contestant: CompetitionContestantCreate,
    current_user: dict = Depends(get_current_user)
):
    """تسجيل طالب كمتسابق في مسابقة قرآنية"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    comp_obj_id = safe_object_id(comp_id)
    comp = await db.competitions.find_one({"_id": comp_obj_id})
    if not comp:
        raise HTTPException(status_code=404, detail="المسابقة القرآنية غير موجودة")
        
    student_obj_id = safe_object_id(contestant.student_id)
    student = await db.students.find_one({"_id": student_obj_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
        
    center_id = current_user.get("center_id")
    if current_user["role"] not in ["admin", "super_admin"] and student.get("center_id") != center_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بتسجيل طالب من مركز آخر")
        
    existing = await db.competition_contestants.find_one({
        "competition_id": comp_id,
        "student_id": contestant.student_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="الطالب مسجل بالفعل في هذه المسابقة")
        
    con_dict = contestant.model_dump()
    con_dict["competition_id"] = comp_id
    con_dict["center_id"] = center_id or student.get("center_id")
    con_dict["grades"] = None
    con_dict["total_score"] = 0.0
    con_dict["created_at"] = datetime.utcnow()
    
    result = await db.competition_contestants.insert_one(con_dict)
    
    return {
        **con_dict,
        "id": str(result.inserted_id),
        "student_name": student.get("name")
    }

@router.get("/api/competitions/{comp_id}/contestants", response_model=List[CompetitionContestantResponse])
async def get_contestants(comp_id: str, current_user: dict = Depends(get_current_user)):
    """عرض المتسابقين المسجلين في المسابقة القرآنية مع درجاتهم"""
    comp_obj_id = safe_object_id(comp_id)
    comp = await db.competitions.find_one({"_id": comp_obj_id})
    if not comp:
        raise HTTPException(status_code=404, detail="المسابقة القرآنية غير موجودة")
        
    role = current_user["role"]
    center_id = current_user.get("center_id")
    if role not in ["admin", "super_admin"] and comp.get("center_id") != center_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بعرض متسابقي مركز آخر")
        
    query = {"competition_id": comp_id}
    contestants = await db.competition_contestants.find(query).sort("total_score", -1).to_list(200)
    
    student_ids = list(set([c.get("student_id") for c in contestants]))
    students_map = {}
    if student_ids:
        students_cursor = db.students.find({"_id": {"$in": [safe_object_id(sid) for sid in student_ids]}})
        async for s in students_cursor:
            students_map[str(s["_id"])] = s.get("name")
            
    result = []
    for c in contestants:
        item = serialize_doc(c)
        item["student_name"] = students_map.get(c.get("student_id"), "طالب غير معروف")
        result.append(item)
        
    return result

@router.post("/api/competitions/contestants/{contestant_id}/grade", response_model=CompetitionContestantResponse)
async def grade_contestant(
    contestant_id: str,
    grades: ContestantGrades,
    current_user: dict = Depends(get_current_user)
):
    """رصد وتقييم درجات المتسابق في المسابقة القرآنية"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    con_obj_id = safe_object_id(contestant_id)
    contestant = await db.competition_contestants.find_one({"_id": con_obj_id})
    if not contestant:
        raise HTTPException(status_code=404, detail="المتسابق غير موجود")
        
    center_id = current_user.get("center_id")
    if current_user["role"] not in ["admin", "super_admin"] and contestant.get("center_id") != center_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بتقييم متسابق لمركز آخر")
        
    if grades.hifdh_score > 70 or grades.hifdh_score < 0:
        raise HTTPException(status_code=400, detail="درجة الحفظ يجب أن تكون بين 0 و 70")
    if grades.tajweed_score > 20 or grades.tajweed_score < 0:
        raise HTTPException(status_code=400, detail="درجة أحكام التجويد يجب أن تكون بين 0 و 20")
    if grades.voice_score > 10 or grades.voice_score < 0:
        raise HTTPException(status_code=400, detail="درجة حسن الصوت والأداء يجب أن تكون بين 0 و 10")
        
    total = round(grades.hifdh_score + grades.tajweed_score + grades.voice_score, 2)
    
    await db.competition_contestants.update_one(
        {"_id": con_obj_id},
        {"$set": {"grades": grades.model_dump(), "total_score": total}}
    )
    
    updated = await db.competition_contestants.find_one({"_id": con_obj_id})
    student = await db.students.find_one({"_id": safe_object_id(updated.get("student_id"))})
    
    return {
        **serialize_doc(updated),
        "student_name": student.get("name") if student else "طالب غير معروف"
    }
