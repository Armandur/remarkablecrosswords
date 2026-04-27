import asyncio

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, get_setting, set_setting
from app.deps import require_admin, get_current_user
from app.config import REMARKABLE_FOLDER
from app.services.remarkable import get_remarkable_client

router = APIRouter(prefix="/api/remarkable", tags=["remarkable-api"])

class PathBody(BaseModel):
    path: str

class FolderBody(BaseModel):
    folder: str

@router.get("/ls")
async def ls(path: str = "/", user=Depends(get_current_user)):
    client = get_remarkable_client()
    try:
        items = await asyncio.to_thread(client.ls_detailed, path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    items_sorted = sorted(items, key=lambda x: (not x["is_dir"], x["name"].lower()))
    return {"path": path, "items": items_sorted}

@router.post("/mkdir")
async def mkdir(body: PathBody, user=Depends(require_admin)):
    client = get_remarkable_client()
    ok = await asyncio.to_thread(client.ensure_folder, body.path)
    if not ok:
        raise HTTPException(status_code=502, detail="Kunde inte skapa mapp")
    return {"ok": True}

@router.post("/rm")
async def rm(body: PathBody, user=Depends(require_admin)):
    client = get_remarkable_client()
    ok = await asyncio.to_thread(client.rm, body.path)
    if not ok:
        raise HTTPException(status_code=502, detail="Kunde inte ta bort")
    return {"ok": True}

@router.get("/folder")
async def get_folder(db: Session = Depends(get_db), user=Depends(get_current_user)):
    folder = get_setting(db, "remarkable_folder", REMARKABLE_FOLDER)
    return {"folder": folder}

@router.post("/folder")
async def set_folder(body: FolderBody, db: Session = Depends(get_db), user=Depends(require_admin)):
    set_setting(db, "remarkable_folder", body.folder)
    return {"ok": True, "folder": body.folder}
