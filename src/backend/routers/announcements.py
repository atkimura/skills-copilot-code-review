"""
Announcement endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from datetime import datetime

from bson import ObjectId
from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def serialize_announcement(doc):
    """Convert MongoDB document to JSON-serializable dict"""
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("", response_model=List[Dict[str, Any]])
def get_announcements() -> List[Dict[str, Any]]:
    """Get all active (non-expired) announcements"""
    now = datetime.utcnow().isoformat()
    query = {
        "expiration_date": {"$gte": now},
        "$or": [
            {"start_date": {"$exists": False}},
            {"start_date": None},
            {"start_date": ""},
            {"start_date": {"$lte": now}},
        ]
    }
    results = []
    for doc in announcements_collection.find(query).sort("created_at", -1):
        results.append(serialize_announcement(doc))
    return results


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str = Query(...)) -> List[Dict[str, Any]]:
    """Get all announcements (including expired) for management - requires auth"""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    results = []
    for doc in announcements_collection.find().sort("created_at", -1):
        results.append(serialize_announcement(doc))
    return results


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    title: str = Query(...),
    message: str = Query(...),
    expiration_date: str = Query(...),
    start_date: Optional[str] = Query(None),
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """Create a new announcement - requires teacher authentication"""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Validate expiration_date is in the future
    try:
        exp = datetime.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expiration date format")

    if exp < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Expiration date must be in the future")

    doc = {
        "title": title,
        "message": message,
        "expiration_date": expiration_date,
        "start_date": start_date or "",
        "created_by": teacher_username,
        "created_at": datetime.utcnow().isoformat()
    }

    result = announcements_collection.insert_one(doc)
    doc["id"] = str(result.inserted_id)
    doc.pop("_id", None)
    return doc


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    title: str = Query(...),
    message: str = Query(...),
    expiration_date: str = Query(...),
    start_date: Optional[str] = Query(None),
    teacher_username: str = Query(...)
) -> Dict[str, Any]:
    """Update an existing announcement - requires teacher authentication"""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    existing = announcements_collection.find_one({"_id": obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")

    try:
        datetime.fromisoformat(expiration_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid expiration date format")

    update_data = {
        "title": title,
        "message": message,
        "expiration_date": expiration_date,
        "start_date": start_date or "",
    }

    announcements_collection.update_one({"_id": obj_id}, {"$set": update_data})

    updated = announcements_collection.find_one({"_id": obj_id})
    return serialize_announcement(updated)


@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: str,
    teacher_username: str = Query(...)
):
    """Delete an announcement - requires teacher authentication"""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        obj_id = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")

    result = announcements_collection.delete_one({"_id": obj_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted successfully"}
