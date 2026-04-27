import os
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import Crossword, Issue, Job, Source, get_db
from app.deps import templates, get_current_user
from app.scheduler import run_sync_job
from app.csrf import CsrfProtect

router = APIRouter(prefix="/crosswords", tags=["crosswords"])

@router.get("/")
async def list_crosswords(
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
    source_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    synced: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
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

    total = query.count()
    crosswords = query.order_by(Issue.published_at.desc(), Crossword.id.desc()).offset(offset).limit(limit).all()
    sources = db.query(Source).order_by(Source.name).all()

    import urllib.parse
    base_params = urllib.parse.urlencode({k: v for k, v in {
        "source_id": source_id or "", "from_date": from_date or "",
        "to_date": to_date or "", "synced": synced or "", "limit": limit,
    }.items() if v != ""})

    return templates.TemplateResponse(request, "crosswords/list.html", {
        "crosswords": crosswords, "sources": sources,
        "source_id": source_id, "from_date": from_date,
        "to_date": to_date, "synced": synced,
        "offset": offset, "limit": limit, "total": total,
        "base_params": base_params,
    })

@router.post("/{crossword_id}/sync")
async def sync_crossword(crossword_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), user=Depends(get_current_user), _csrf: CsrfProtect = Depends(CsrfProtect())):
    cw = db.query(Crossword).filter(Crossword.id == crossword_id).first()
    if not cw:
        return JSONResponse({"error": "not found"}, status_code=404)
    issue = db.query(Issue).filter(Issue.id == cw.issue_id).first()
    job = Job(kind='sync', state='running', source_id=issue.source_id, issue_id=issue.id)
    db.add(job)
    db.commit()
    background_tasks.add_task(run_sync_job, crossword_id, job.id)
    return JSONResponse({"job_id": job.id})

@router.get("/page")
async def crosswords_page(
    offset: int = 0,
    limit: int = 20,
    source_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    synced: Optional[str] = None,
    sort_by: Optional[str] = "date",
    sort_dir: Optional[str] = "desc",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from fastapi.responses import JSONResponse
    query = db.query(Crossword, Issue, Source) \
        .join(Issue, Crossword.issue_id == Issue.id) \
        .join(Source, Issue.source_id == Source.id)
    if source_id:
        query = query.filter(Source.id == source_id)
    if from_date:
        try:
            query = query.filter(Issue.published_at >= datetime.strptime(from_date, "%Y-%m-%d"))
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
    total = query.count()
    _sort_cols = {
        "name": Issue.name, "source": Source.name,
        "date": Issue.published_at, "synced": Crossword.synced_at,
    }
    _col = _sort_cols.get(sort_by, Issue.published_at)
    _order = _col.asc() if sort_dir == "asc" else _col.desc()
    rows = query.order_by(_order, Crossword.id.desc()).offset(offset).limit(limit).all()
    return JSONResponse({
        "total": total, "offset": offset, "limit": limit,
        "crosswords": [
            {
                "id": cw.id,
                "name": issue.name,
                "source": source.name,
                "published_at": issue.published_at.isoformat() if issue.published_at else None,
                "synced_at": cw.synced_at.isoformat() if cw.synced_at else None,
                "has_pdf": bool(cw.pdf_path),
            }
            for cw, issue, source in rows
        ],
    })

@router.post("/{crossword_id}/delete")
async def delete_crossword(crossword_id: int, db: Session = Depends(get_db), user=Depends(get_current_user), _csrf: CsrfProtect = Depends(CsrfProtect())):
    cw = db.query(Crossword).filter(Crossword.id == crossword_id).first()
    if not cw:
        return JSONResponse({"ok": False}, status_code=404)
    if cw.pdf_path:
        try:
            os.remove(cw.pdf_path)
        except (FileNotFoundError, OSError):
            pass
    db.delete(cw)
    db.commit()
    return JSONResponse({"ok": True})

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
