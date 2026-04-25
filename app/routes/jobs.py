from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session

from app.database import Job, get_db
from app.deps import templates, get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/")
async def list_jobs(
    request: Request,
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    jobs = db.query(Job).order_by(Job.started_at.desc()).offset(offset).limit(limit).all()
    total = db.query(Job).count()
    return templates.TemplateResponse(
        request,
        "jobs/list.html",
        {"jobs": jobs, "offset": offset, "limit": limit, "total": total},
    )

@router.get("/{job_id}/status")
async def job_status(job_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from fastapi.responses import JSONResponse
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"id": job.id, "state": job.state})

@router.get("/{job_id}")
async def job_detail(job_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id).first()
    return templates.TemplateResponse(request, "jobs/detail.html", {"job": job})
