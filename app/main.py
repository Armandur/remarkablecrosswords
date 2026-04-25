from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import (
    SESSION_SECRET_KEY,
    DATA_DIR,
    PDF_INCOMING_DIR,
    PDF_CROSSWORDS_DIR,
    PDF_SYNCED_DIR,
    QUEUE_DIR,
)
from app.database import init_db, SessionLocal
from app.auth import ensure_first_admin
from app.routes import auth, dashboard, sources, crosswords, jobs, settings
from app.scheduler import setup_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Skapa kataloger
    for d in [DATA_DIR, PDF_INCOMING_DIR, PDF_CROSSWORDS_DIR, PDF_SYNCED_DIR, QUEUE_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    
    # Initiera databas
    init_db()
    
    # Säkerställ första admin
    db = SessionLocal()
    try:
        ensure_first_admin(db)
    finally:
        db.close()
    
    # Setup scheduler
    scheduler = setup_scheduler(app)
        
    yield
    
    # Shutdown scheduler
    scheduler.shutdown()

app = FastAPI(title="remarkablecrosswords", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    max_age=3600 * 24 * 30,  # 30 dagar
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Routers
app.include_router(auth.router, tags=["auth"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(sources.router, tags=["sources"])
app.include_router(crosswords.router, tags=["crosswords"])
app.include_router(jobs.router, tags=["jobs"])
app.include_router(settings.router, tags=["settings"])
