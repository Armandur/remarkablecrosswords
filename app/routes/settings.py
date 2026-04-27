import json
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import NotificationTarget, get_db, get_setting, set_setting
from app.deps import templates, require_admin, get_current_user
from app.config import REMARKABLE_CLIENT, REMARKABLE_FOLDER, DEFAULT_TIMEZONE
from app.services.remarkable import is_rmapi_authenticated, register_remarkable
from app.services.notifier import build_notifier, NOTIFICATION_EVENTS, TEST_MESSAGES, NOTIFIER_KINDS
from app.csrf import CsrfProtect

router = APIRouter(prefix="/settings", tags=["settings"])

@router.get("/")
async def settings_view(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    raw_targets = db.query(NotificationTarget).all()
    targets = []
    for t in raw_targets:
        try:
            cfg = json.loads(t.config_json)
        except Exception:
            cfg = {}
        try:
            events = json.loads(t.events_json or '["all"]')
        except Exception:
            events = ["all"]
        targets.append({
            "id": t.id,
            "kind": t.kind,
            "enabled": t.enabled,
            "config": cfg,
            "events": events,
        })
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "targets": targets,
            "notification_events": NOTIFICATION_EVENTS,
            "notifier_kinds": NOTIFIER_KINDS,
            "remarkable_client": REMARKABLE_CLIENT,
            "rmapi_authenticated": is_rmapi_authenticated(),
            "remarkable_folder": get_setting(db, "remarkable_folder", REMARKABLE_FOLDER),
            "timezone": get_setting(db, "timezone", DEFAULT_TIMEZONE),
            "flash_msg": request.query_params.get("msg"),
            "flash_type": request.query_params.get("msg_type", "success"),
        },
    )

@router.post("/timezone")
async def update_timezone(
    timezone: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
    _csrf: CsrfProtect = Depends(CsrfProtect())
):
    set_setting(db, "timezone", timezone.strip())
    return RedirectResponse(url="/settings?msg=Tidszon+sparad&msg_type=success", status_code=303)

@router.post("/remarkable/connect")
async def connect_remarkable(
    code: str = Form(...),
    user=Depends(require_admin),
    _csrf: CsrfProtect = Depends(CsrfProtect())
):
    ok, msg = register_remarkable(code)
    msg_type = "success" if ok else "danger"
    return RedirectResponse(url=f"/settings?msg={msg}&msg_type={msg_type}", status_code=303)

@router.post("/notifications")
async def add_notification_target(
    request: Request,
    kind: str = Form(...),
    events_json: str = Form('["all"]'),
    enabled: bool = Form(True),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
    _csrf: CsrfProtect = Depends(CsrfProtect())
):
    form_data = await request.form()
    config = {}
    for key, value in form_data.items():
        if key.startswith("cfg_"):
            config[key[4:]] = value
            
    target = NotificationTarget(
        kind=kind, 
        config_json=json.dumps(config), 
        events_json=events_json, 
        enabled=enabled
    )
    db.add(target)
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/notifications/{target_id}/update")
async def update_notification_target(
    request: Request,
    target_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
    _csrf: CsrfProtect = Depends(CsrfProtect())
):
    target = db.query(NotificationTarget).filter(NotificationTarget.id == target_id).first()
    if not target:
        return JSONResponse({"error": "Hittades inte"}, status_code=404)
    
    form_data = await request.form()
    
    try:
        current_config = json.loads(target.config_json)
    except Exception:
        current_config = {}
        
    notifier_class = NOTIFIER_KINDS.get(target.kind)
    password_fields = []
    if notifier_class:
        password_fields = [f["name"] for f in notifier_class.CONFIG_FIELDS if f["type"] == "password"]
    
    new_config = {}
    for key, value in form_data.items():
        if key.startswith("cfg_"):
            field_name = key[4:]
            if field_name in password_fields and not value:
                # Keep existing value for empty password fields
                new_config[field_name] = current_config.get(field_name, "")
            else:
                new_config[field_name] = value
                
    target.config_json = json.dumps(new_config)
    db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/notifications/{target_id}/test")
async def test_notification_target(
    target_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
    _csrf: CsrfProtect = Depends(CsrfProtect())
):
    target = db.query(NotificationTarget).filter(NotificationTarget.id == target_id).first()
    if not target:
        return JSONResponse({"ok": False, "error": "Hittades inte"}, status_code=404)
    notifier = build_notifier(target)
    if not notifier:
        return JSONResponse({"ok": False, "error": f"Okänd typ: {target.kind}"})
    results = {}
    for event_key, msg in TEST_MESSAGES.items():
        results[event_key] = notifier.send(msg["title"], msg["message"])
    return JSONResponse({"ok": all(results.values()), "results": results})

@router.post("/notifications/{target_id}/events")
async def update_notification_events(
    target_id: int,
    events_json: str = Form('["all"]'),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
    _csrf: CsrfProtect = Depends(CsrfProtect())
):
    target = db.query(NotificationTarget).filter(NotificationTarget.id == target_id).first()
    if not target:
        return JSONResponse({"ok": False}, status_code=404)
    target.events_json = events_json
    db.commit()
    return JSONResponse({"ok": True})

@router.post("/notifications/{target_id}/delete")
async def delete_notification_target(target_id: int, db: Session = Depends(get_db), user=Depends(require_admin), _csrf: CsrfProtect = Depends(CsrfProtect())):
    target = db.query(NotificationTarget).filter(NotificationTarget.id == target_id).first()
    if target:
        db.delete(target)
        db.commit()
    return RedirectResponse(url="/settings", status_code=303)

@router.post("/notifications/{target_id}/toggle")
async def toggle_notification_target(target_id: int, db: Session = Depends(get_db), user=Depends(require_admin), _csrf: CsrfProtect = Depends(CsrfProtect())):
    target = db.query(NotificationTarget).filter(NotificationTarget.id == target_id).first()
    if target:
        target.enabled = not target.enabled
        db.commit()
    return RedirectResponse(url="/settings", status_code=303)
