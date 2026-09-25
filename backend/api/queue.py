from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.security import get_current_staff
from database.session import get_db
from schemas.queue import TokenRequest
from services.queue_service import queue_service

router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.post("/token")
def generate_token(req: TokenRequest, staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    return queue_service.add_token(db, req.customer_name, req.service_type, req.customer_type)


@router.get("")
def get_queue(staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    return queue_service.get_state(db)


@router.post("/call-next")
def call_next(staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    token = queue_service.call_next(db)
    if not token:
        return {"message": "Queue is empty"}
    return token
