from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.security import get_current_staff
from core.config import settings
from database.models import SchemeAlert, SchemeDraft, SchemeUpdateRun
from database.session import get_db
from services import scheme_alert_service as alerts
from services import scheme_update_service as svc
from services.eligibility_service import load_catalogue

router = APIRouter(prefix="/api/schemes", tags=["scheme-updates"])


class RulesEdit(BaseModel):
    collateral_any: list[str] | None = None
    occupations: list[str] | None = None
    purposes: list[str] | None = None
    min_age: int | None = None
    max_age: int | None = None


class DraftEdits(BaseModel):
    name_en: str | None = Field(default=None, max_length=120)
    summary_en: str | None = Field(default=None, max_length=600)
    kind: Literal["bank_product", "government_scheme"] | None = None
    rules: RulesEdit | None = None
    documents: list[str] | None = None
    valid_until: str | None = None
    staff_checks: list[str] | None = None


class ReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=500)


def _review_error(exc: svc.ReviewError) -> HTTPException:
    status = 404 if str(exc) == "Draft not found" else 409 if not exc.issues else 422
    return HTTPException(status, {"message": str(exc), "issues": exc.issues})


@router.get("/updates/status")
def update_status(staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    last = db.query(SchemeUpdateRun).order_by(SchemeUpdateRun.id.desc()).first()
    counts = {s: db.query(SchemeDraft).filter(SchemeDraft.status == s).count() for s in ("pending", "approved", "rejected")}
    counts["alerts_new"] = db.query(SchemeAlert).filter(SchemeAlert.status == "new").count()
    return {
        "last_run": svc.serialize_run(last),
        "counts": counts,
        "auto_update": settings.SCHEME_AUTO_UPDATE,
        "interval_hours": settings.SCHEME_UPDATE_INTERVAL_HOURS,
        "extraction_mode": settings.SCHEME_EXTRACTION_MODE if settings.GROQ_API_KEY else "preset",
    }


@router.post("/updates/run")
def run_now(staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    return svc.serialize_run(svc.run_update(db, trigger="manual"))


@router.get("/updates")
def list_drafts(status: Literal["pending", "approved", "rejected"] = "pending", staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    drafts = db.query(SchemeDraft).filter(SchemeDraft.status == status).order_by(SchemeDraft.published_on.desc()).all()
    return [svc.serialize_draft(d) for d in drafts]


@router.patch("/updates/{draft_id}")
def edit_draft(draft_id: int, edits: DraftEdits, staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    try:
        d = svc.save_edits(db, draft_id, edits.model_dump(exclude_unset=True))
    except svc.ReviewError as exc:
        raise _review_error(exc)
    return svc.serialize_draft(d)


@router.post("/updates/{draft_id}/approve")
def approve_draft(draft_id: int, req: ReviewRequest, staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    try:
        d = svc.approve(db, draft_id, staff, req.note)
    except svc.ReviewError as exc:
        raise _review_error(exc)
    matched = db.query(SchemeAlert).filter(SchemeAlert.draft_id == d.id).count()
    return {**svc.serialize_draft(d), "customers_matched": matched}


@router.post("/updates/{draft_id}/reject")
def reject_draft(draft_id: int, req: ReviewRequest, staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    try:
        d = svc.reject(db, draft_id, staff, req.note)
    except svc.ReviewError as exc:
        raise _review_error(exc)
    return svc.serialize_draft(d)


@router.get("/options")
def options(staff: str = Depends(get_current_staff)):
    """Allowed values for the review form."""
    from services.eligibility_service import ASSET_TYPES, OCCUPATIONS

    return {
        "collateral": list(ASSET_TYPES),
        "occupations": list(OCCUPATIONS),
        "purposes": list(svc.PURPOSE_RULES),
        "documents": sorted(svc.known_documents()),
        "kinds": list(svc.KINDS),
    }


@router.get("/catalogue")
def catalogue(staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    """Everything the customer eligibility checker currently uses."""
    base = [{"id": s["id"], "name": s["name"]["en"], "kind": s["kind"], "origin": "base"} for s in load_catalogue()["schemes"]]
    added = [
        {"id": s["id"], "name": s["name"]["en"], "kind": s["kind"], "origin": "daily_update", "added_on": s.get("added_on"), "valid_until": s.get("valid_until")}
        for s in svc.get_approved_schemes(db)
    ]
    return {"schemes": added + base}


class AlertUpdate(BaseModel):
    status: Literal["contacted", "not_suitable", "new"]
    note: str | None = Field(default=None, max_length=500)


@router.get("/alerts")
def list_alerts(status: Literal["new", "contacted", "not_suitable"] = "new", staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    rows = db.query(SchemeAlert).filter(SchemeAlert.status == status).order_by(SchemeAlert.created_at.desc()).all()
    return [alerts.serialize_alert(a) for a in rows]


@router.post("/alerts/rescan")
def rescan(staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    """Re-check all approved schemes against customer profiles."""
    return {"created": alerts.rescan_all(db)}


@router.post("/alerts/{alert_id}")
def update_alert(alert_id: int, req: AlertUpdate, staff: str = Depends(get_current_staff), db: Session = Depends(get_db)):
    a = alerts.update_alert(db, alert_id, req.status, staff, req.note)
    if not a:
        raise HTTPException(404, "Alert not found")
    return alerts.serialize_alert(a)
