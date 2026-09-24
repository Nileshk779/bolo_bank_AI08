from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.security import get_current_staff
from database.session import get_db
from services import analytics_service

router = APIRouter(prefix="/api/dashboard", tags=["branch-dashboard"])


@router.get("/summary")
def dashboard_summary(days: int = Query(7, ge=1, le=90), staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    return analytics_service.summary(db, days=days)


@router.post("/demo-data")
def add_demo_data(staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    """Loads two weeks of clearly-flagged sample activity for presentations."""
    return {"created": analytics_service.generate_demo_data(db)}


@router.delete("/demo-data")
def delete_demo_data(staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    return {"removed": analytics_service.remove_demo_data(db)}
