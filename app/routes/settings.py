import json
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import NotificationTarget, get_db
from app.deps import templates, require_admin, get_current_user
from app.config import REMARKABLE_CLIENT

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/")
async def settings_view(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    targets = db.query(NotificationTarget).all()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"targets": targets, "remarkable_client": REMARKABLE_CLIENT},
    )

@router.post("/notifications")
async def add_notification_target(
    kind: str = Form(...),
    config_json: str = Form("{}"),
    enabled: bool = Form(True),
    db: Session = Depends(get_db),
    user=Depends(require_admin)
):
    target = NotificationTarget(kind=kind, config_json=config_json, enabled=enabled)
    db.add(target)
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/notifications/{target_id}/delete")
async def delete_notification_target(target_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    target = db.query(NotificationTarget).filter(NotificationTarget.id == target_id).first()
    if target:
        db.delete(target)
        db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/notifications/{target_id}/toggle")
async def toggle_notification_target(target_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    target = db.query(NotificationTarget).filter(NotificationTarget.id == target_id).first()
    if target:
        target.enabled = not target.enabled
        db.commit()
    return RedirectResponse(url="/settings", status_code=303)
