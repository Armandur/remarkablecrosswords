import json
from fastapi import APIRouter, Depends, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import Source, get_db
from app.deps import templates, require_admin, get_current_user
from app.scheduler import run_pipeline_for_source

router = APIRouter(prefix="/sources", tags=["sources"])

@router.get("/")
async def list_sources(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sources = db.query(Source).all()
    return templates.TemplateResponse("sources/list.html", {"request": request, "sources": sources})

@router.get("/new")
async def new_source_form(request: Request, user=Depends(require_admin)):
    return templates.TemplateResponse("sources/form.html", {"request": request})

@router.post("")
async def create_source(
    name: str = Form(...),
    kind: str = Form(...),
    enabled: bool = Form(True),
    schedule_cron: str = Form(None),
    prefix: str = Form(None),
    config_json: str = Form("{}"),
    db: Session = Depends(get_db),
    user=Depends(require_admin)
):
    source = Source(
        name=name,
        kind=kind,
        enabled=enabled,
        schedule_cron=schedule_cron,
        prefix=prefix,
        config_json=config_json
    )
    db.add(source)
    db.commit()
    return RedirectResponse(url="/sources", status_code=303)

@router.get("/{source_id}")
async def source_detail(source_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    source = db.query(Source).filter(Source.id == source_id).first()
    return templates.TemplateResponse("sources/detail.html", {"request": request, "source": source})

@router.post("/{source_id}/run")
async def run_source(source_id: int, background_tasks: BackgroundTasks, user=Depends(require_admin)):
    background_tasks.add_task(run_pipeline_for_source, source_id)
    return RedirectResponse(url="/jobs", status_code=303)

@router.post("/{source_id}/toggle")
async def toggle_source(source_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if source:
        source.enabled = not source.enabled
        db.commit()
    return RedirectResponse(url=f"/sources/{source_id}", status_code=303)

@router.post("/{source_id}/delete")
async def delete_source(source_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    source = db.query(Source).filter(Source.id == source_id).first()
    if source:
        db.delete(source)
        db.commit()
    return RedirectResponse(url="/sources", status_code=303)
