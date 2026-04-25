from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import Crossword, Job, Source, get_db
from app.deps import templates
from app.auth import get_current_user_id

router = APIRouter()

@router.get("/")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user_id = get_current_user_id(request)
    if not user_id:
        return RedirectResponse(url="/login")
    
    latest_jobs = db.query(Job).order_by(Job.started_at.desc()).limit(10).all()
    pending_sync_count = db.query(Crossword).filter(Crossword.synced_at == None).count()
    active_sources = db.query(Source).filter(Source.enabled == True).all()
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "latest_jobs": latest_jobs,
            "pending_sync_count": pending_sync_count,
            "active_sources": active_sources
        }
    )
