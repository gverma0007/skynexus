from fastapi import APIRouter, Depends
from app.services.clock import clock
from datetime import datetime

router = APIRouter()

@router.get("/time")
async def get_current_time():
    return {"current_time": clock.get_time()}

@router.post("/advance")
async def advance_time(hours: int):
    clock.advance(hours)
    return {"current_time": clock.get_time()}
