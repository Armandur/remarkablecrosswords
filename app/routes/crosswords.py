from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import Crossword, Issue, Job, Source, get_db
from app.deps import templates, get_current_user
from app.scheduler import run_sync_job

router = APIRouter(prefix="/crosswords", tags=["crosswords"])

@router.get("/")
async def list_crosswords(
    request: Request, 
    db: Session = Depends(get_db), 
    user=Depends(get_current_user),
    source_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    synced: Optional[str] = None
):
    query = db.query(Crossword, Issue, Source).join(Issue, Crossword.issue_id == Issue.id).join(Source, Issue.source_id == Source.id)

    if source_id:
        query = query.filter(Source.id == source_id)
    
    if from_date:
        try:
            dt_from = datetime.strptime(from_date, "%Y-%m-%d")
            query = query.filter(Issue.published_at >= dt_from)
        except ValueError:
            pass
            
    if to_date:
        try:
            dt_to = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            query = query.filter(Issue.published_at <= dt_to)
        except ValueError:
            pass

    if synced == 'yes':
        query = query.filter(Crossword.synced_at.isnot(None))
    elif synced == 'no':
        query = query.filter(Crossword.synced_at.is_(None))

    crosswords = query.order_by(Issue.published_at.desc(), Crossword.id.desc()).all()
    sources = db.query(Source).order_by(Source.name).all()

    return templates.TemplateResponse(request, "crosswords/list.html", {
        "crosswords": crosswords,
        "sources": sources,
        "source_id": source_id,
        "from_date": from_date,
        "to_date": to_date,
        "synced": synced
    })

@router.post("/{crossword_id}/sync")
async def sync_crossword(crossword_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cw = db.query(Crossword).filter(Crossword.id == crossword_id).first()
    if not cw:
        return JSONResponse({"error": "not found"}, status_code=404)
    issue = db.query(Issue).filter(Issue.id == cw.issue_id).first()
    job = Job(kind='sync', state='running', source_id=issue.source_id, issue_id=issue.id)
    db.add(job)
    db.commit()
    background_tasks.add_task(run_sync_job, crossword_id, job.id)
    return JSONResponse({"job_id": job.id})

@router.get("/{crossword_id}/view")
async def view_crossword(crossword_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cw = db.query(Crossword).filter(Crossword.id == crossword_id).first()
    if cw and cw.pdf_path:
        return FileResponse(cw.pdf_path, media_type="application/pdf")
    return RedirectResponse(url="/crosswords")

@router.get("/{crossword_id}/download")
async def download_crossword(crossword_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cw = db.query(Crossword).filter(Crossword.id == crossword_id).first()
    if cw and cw.pdf_path:
        filename = Path(cw.pdf_path).name
        return FileResponse(cw.pdf_path, filename=filename)
    return RedirectResponse(url="/crosswords")
