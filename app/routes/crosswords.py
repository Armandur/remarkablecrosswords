from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import Crossword, Issue, Source, get_db
from app.deps import templates, get_current_user
from app.scheduler import sync_single_crossword

router = APIRouter(prefix="/crosswords", tags=["crosswords"])

@router.get("/")
async def list_crosswords(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    crosswords = db.query(Crossword, Issue, Source).join(Issue, Crossword.issue_id == Issue.id).join(Source, Issue.source_id == Source.id).order_by(Issue.published_at.desc(), Crossword.id.desc()).all()
    return templates.TemplateResponse(request, "crosswords/list.html", {"crosswords": crosswords})

@router.post("/{crossword_id}/sync")
async def sync_crossword(crossword_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    sync_single_crossword(db, crossword_id)
    return RedirectResponse(url="/crosswords", status_code=303)

@router.get("/{crossword_id}/download")
async def download_crossword(crossword_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    cw = db.query(Crossword).filter(Crossword.id == crossword_id).first()
    if cw and cw.pdf_path:
        return FileResponse(cw.pdf_path, filename=f"crossword_{crossword_id}.pdf")
    return RedirectResponse(url="/crosswords")
