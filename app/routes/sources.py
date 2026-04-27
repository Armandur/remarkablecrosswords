import json
import os
from fastapi import APIRouter, Depends, Request, Form, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import Source, Issue, Crossword, get_db, get_setting
from app.deps import templates, require_admin, get_current_user
from app.scheduler import run_pipeline_for_source, rerender_issues_for_source
from app.config import DEFAULT_TIMEZONE
from app.csrf import CsrfProtect

router = APIRouter(prefix="/sources", tags=["sources"])

@router.get("/")
async def list_sources(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sources = db.query(Source).all()
    return templates.TemplateResponse(request, "sources/list.html", {"sources": sources})

@router.get("/new")
async def new_source_form(request: Request, db: Session = Depends(get_db), user=Depends(require_admin)):
    tz = get_setting(db, "timezone", DEFAULT_TIMEZONE)
    return templates.TemplateResponse(request, "sources/form.html", {"timezone": tz})

@router.post("/")
async def create_source(
    name: str = Form(...),
    kind: str = Form(...),
    enabled: bool = Form(True),
    schedule_cron: str = Form(None),
    prefix: str = Form(None),
    config_json: str = Form("{}"),
    overwrite: bool = Form(False),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
    _csrf: CsrfProtect = Depends(CsrfProtect())
):
    source = Source(
        name=name,
        kind=kind,
        enabled=enabled,
        schedule_cron=schedule_cron,
        prefix=prefix,
        config_json=config_json,
        overwrite=overwrite,
    )
    db.add(source)
    db.commit()
    return RedirectResponse(url="/sources", status_code=303)

@router.get("/{source_id}")
async def source_detail(source_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    source = db.query(Source).filter(Source.id == source_id).first()
    return templates.TemplateResponse(request, "sources/detail.html", {"source": source})

@router.get("/{source_id}/edit")
async def edit_source_form(source_id: int, request: Request, db: Session = Depends(get_db), user=Depends(require_admin)):
    source = db.query(Source).filter(Source.id == source_id).first()
    tz = get_setting(db, "timezone", DEFAULT_TIMEZONE)
    return templates.TemplateResponse(request, "sources/form.html", {"source": source, "timezone": tz})

@router.post("/{source_id}/edit")
async def update_source(
    source_id: int,
    name: str = Form(...),
    kind: str = Form(...),
    schedule_cron: str = Form(None),
    prefix: str = Form(None),
    config_json: str = Form("{}"),
    overwrite: bool = Form(False),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
    _csrf: CsrfProtect = Depends(CsrfProtect())
):
    source = db.query(Source).filter(Source.id == source_id).first()
    if source:
        source.name = name
        source.kind = kind
        source.schedule_cron = schedule_cron
        source.prefix = prefix
        source.config_json = config_json
        source.overwrite = overwrite
        db.commit()
    return RedirectResponse(url=f"/sources/{source_id}", status_code=303)

@router.post("/{source_id}/run")
async def run_source(source_id: int, background_tasks: BackgroundTasks, user=Depends(require_admin), _csrf: CsrfProtect = Depends(CsrfProtect())):
    background_tasks.add_task(run_pipeline_for_source, source_id)
    return RedirectResponse(url="/jobs", status_code=303)

@router.post("/{source_id}/rerender")
async def rerender_source(source_id: int, background_tasks: BackgroundTasks, user=Depends(require_admin), _csrf: CsrfProtect = Depends(CsrfProtect())):
    background_tasks.add_task(rerender_issues_for_source, source_id)
    return RedirectResponse(url="/jobs", status_code=303)

@router.post("/{source_id}/toggle")
async def toggle_source(source_id: int, db: Session = Depends(get_db), user=Depends(require_admin), _csrf: CsrfProtect = Depends(CsrfProtect())):
    source = db.query(Source).filter(Source.id == source_id).first()
    if source:
        source.enabled = not source.enabled
        db.commit()
    return RedirectResponse(url=f"/sources/{source_id}", status_code=303)

@router.post("/{source_id}/clear-cache")
async def clear_source_cache(source_id: int, db: Session = Depends(get_db), user=Depends(require_admin), _csrf: CsrfProtect = Depends(CsrfProtect())):
    issues = db.query(Issue).filter(Issue.source_id == source_id).all()
    issue_ids = [i.id for i in issues]
    if issue_ids:
        crosswords = db.query(Crossword).filter(Crossword.issue_id.in_(issue_ids)).all()
        for cw in crosswords:
            if cw.pdf_path:
                try:
                    os.remove(cw.pdf_path)
                except (FileNotFoundError, OSError):
                    pass
            db.delete(cw)
    for issue in issues:
        if issue.pdf_path:
            try:
                os.remove(issue.pdf_path)
            except (FileNotFoundError, OSError):
                pass
        issue.state = 'pending'
        issue.pdf_path = None
        issue.downloaded_at = None
    db.commit()
    return RedirectResponse(url=f"/sources/{source_id}", status_code=303)

@router.post("/{source_id}/delete")
async def delete_source(source_id: int, db: Session = Depends(get_db), user=Depends(require_admin), _csrf: CsrfProtect = Depends(CsrfProtect())):
    source = db.query(Source).filter(Source.id == source_id).first()
    if source:
        db.delete(source)
        db.commit()
    return RedirectResponse(url="/sources", status_code=303)
