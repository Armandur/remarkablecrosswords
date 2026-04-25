import datetime
import json
from typing import Generator
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine
from sqlalchemy import inspect

from app.config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)  # 'korsordio' | 'prenly'
    enabled = Column(Boolean, default=True)
    schedule_cron = Column(String, nullable=True)
    prefix = Column(String, nullable=True)  # reMarkable-mapp under REMARKABLE_FOLDER
    config_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Issue(Base):
    __tablename__ = "issues"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=False)
    external_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=True)
    pdf_path = Column(String, nullable=True)
    downloaded_at = Column(DateTime, nullable=True)
    state = Column(String, default="pending")  # pending | downloaded | failed

class Crossword(Base):
    __tablename__ = "crosswords"
    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    pdf_path = Column(String, nullable=False)
    pages_json = Column(Text, nullable=True)
    extracted_at = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, nullable=True)
    remarkable_path = Column(String, nullable=True)

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, nullable=False)  # download | extract | sync | notify
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    state = Column(String, nullable=False)  # running | done | failed
    log = Column(Text, nullable=True)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True)

class NotificationTarget(Base):
    __tablename__ = "notification_targets"
    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, nullable=False)
    config_json = Column(Text, default="{}")
    enabled = Column(Boolean, default=True)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    # Säkerställ att mappen finns
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Skapa tabeller om de inte finns
    Base.metadata.create_all(bind=engine)
    
    # ALTER TABLE-guards (exempel på hur man lägger till kolumner senare)
    # inspector = inspect(engine)
    # columns = [c["name"] for c in inspector.get_columns("sources")]
    # with engine.connect() as conn:
    #     if "new_column" not in columns:
    #         conn.execute(text("ALTER TABLE sources ADD COLUMN new_column TEXT"))
    #         conn.commit()
    pass
