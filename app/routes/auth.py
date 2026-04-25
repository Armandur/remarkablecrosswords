"""Auth-routes: login, logout, /api/me."""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_current_user_id, hash_password, verify_password
from app.database import User, get_db
from app.deps import templates
from app.schemas import LoginBody, MePasswordBody

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if get_current_user_id(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/")
    return templates.TemplateResponse(request, "login.html")


@router.post("/api/login")
async def login(body: LoginBody, request: Request, db: Session = Depends(get_db)):
    """Logga in och sätt session."""
    user = db.query(User).filter(User.username == (body.username or "").strip()).first()
    if not user or not verify_password((body.password or ""), user.password_hash):
        raise HTTPException(status_code=401, detail="Fel användarnamn eller lösenord")
    request.session["user_id"] = user.id
    return {"ok": True, "username": user.username, "is_admin": user.is_admin}

@router.post("/api/logout")
async def logout(request: Request):
    """Logga ut – rensa session."""
    request.session.clear()
    return {"ok": True}

@router.get("/api/me")
async def me(current_user: User = Depends(get_current_user)):
    """Aktuell inloggad användare."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "is_admin": current_user.is_admin,
    }

@router.put("/api/me/password")
async def change_my_password(
    body: MePasswordBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Byt eget lösenord – kräver att nuvarande lösenord anges."""
    if not verify_password(body.current_password or "", current_user.password_hash):
        raise HTTPException(status_code=400, detail="Felaktigt nuvarande lösenord")
    new_pw = (body.new_password or "").strip()
    if len(new_pw) < 4:
        raise HTTPException(status_code=400, detail="Det nya lösenordet är för kort (minst 4 tecken)")
    current_user.password_hash = hash_password(new_pw)
    db.commit()
    return {"ok": True}
