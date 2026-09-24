from fastapi import APIRouter, Depends

from auth.security import get_current_staff
from schemas.queue import TokenRequest
from services.queue_service import queue_service

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.post("/token")
async def generate_token(req: TokenRequest, staff: str = Depends(get_current_staff)):
    return queue_service.add_token(req.customer_name, req.service_type, req.customer_type)


@router.get("")
async def get_queue(staff: str = Depends(get_current_staff)):
    return queue_service.get_state()


@router.post("/call-next")
async def call_next(staff: str = Depends(get_current_staff)):
    token = queue_service.call_next()
    if not token:
        return {"message": "Queue is empty"}
    return token
