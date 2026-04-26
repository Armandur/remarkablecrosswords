import urllib.parse

from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from app.database import Job, get_db
from app.deps import templates, get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/")
async def list_jobs(
    request: Request,
    offset: int = 0,
    limit: int = 20,
    state: str = "",
    kind: str = "",
    q: str = "",
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    query = db.query(Job)
    if state:
        query = query.filter(Job.state == state)
    if kind:
        query = query.filter(Job.kind == kind)
    if q:
        query = query.filter(Job.log.contains(q))
    total = query.count()
    jobs = query.order_by(Job.started_at.desc()).offset(offset).limit(limit).all()
    base_params = (
        f"state={urllib.parse.quote(state)}"
        f"&kind={urllib.parse.quote(kind)}"
        f"&q={urllib.parse.quote(q)}"
        f"&limit={limit}"
    )
    return templates.TemplateResponse(
        request,
        "jobs/list.html",
        {
            "jobs": jobs, "offset": offset, "limit": limit, "total": total,
            "filter_state": state, "filter_kind": kind, "filter_q": q,
            "base_params": base_params,
        },
    )

@router.get("/latest")
async def jobs_latest(db: Session = Depends(get_db), user=Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    jobs = db.query(Job).order_by(Job.id.desc()).limit(10).all()
    return JSONResponse([
        {
            "id": j.id,
            "kind": j.kind,
            "state": j.state,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        }
        for j in jobs
    ])

@router.get("/page")
async def jobs_page(
    offset: int = 0, limit: int = 10,
    state: str = "", kind: str = "", q: str = "",
    db: Session = Depends(get_db), user=Depends(get_current_user)
):
    from fastapi.responses import JSONResponse
    query = db.query(Job)
    if state:
        query = query.filter(Job.state == state)
    if kind:
        query = query.filter(Job.kind == kind)
    if q:
        query = query.filter(Job.log.contains(q))
    total = query.count()
    jobs = query.order_by(Job.id.desc()).offset(offset).limit(limit).all()
    return JSONResponse({
        "jobs": [
            {
                "id": j.id,
                "kind": j.kind,
                "state": j.state,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    })

@router.get("/terminal-log")
async def terminal_log(limit: int = 20, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    jobs = db.query(Job).order_by(Job.id.desc()).limit(limit).all()
    jobs = list(reversed(jobs))
    return JSONResponse([
        {
            "id": j.id,
            "kind": j.kind,
            "state": j.state,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "log": j.log or "",
        }
        for j in jobs
    ])

@router.get("/{job_id}/status")
async def job_status(job_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({
        "id": job.id,
        "state": job.state,
        "log": job.log or "",
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    })

@router.get("/{job_id}")
async def job_detail(job_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.database import Crossword
    job = db.query(Job).filter(Job.id == job_id).first()
    crosswords = []
    if job and job.issue_id:
        crosswords = db.query(Crossword).filter(Crossword.issue_id == job.issue_id).all()
    return templates.TemplateResponse(request, "jobs/detail.html", {"job": job, "crosswords": crosswords})
