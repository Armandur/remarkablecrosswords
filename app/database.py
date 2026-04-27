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
    UniqueConstraint,
    event,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine import Engine

from app.config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(engine, "connect")
def _fk_pragma_on(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    schedule_cron = Column(String, nullable=True)
    prefix = Column(String, nullable=True)
    filename_template = Column(String, nullable=True)
    config_json = Column(Text, default="{}")
    overwrite = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))


class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String, nullable=False)
    name = Column(String, nullable=False)
    published_at = Column(DateTime, nullable=True)
    pdf_path = Column(String, nullable=True)
    downloaded_at = Column(DateTime, nullable=True)
    state = Column(String, default="pending")  # pending | downloaded | failed


class Crossword(Base):
    __tablename__ = "crosswords"
    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    pdf_path = Column(String, nullable=False)
    pages_json = Column(Text, nullable=True)
    extracted_at = Column(DateTime, nullable=True)
    synced_at = Column(DateTime, nullable=True)
    remarkable_path = Column(String, nullable=True)


class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, nullable=False)  # download | extract | sync | notify
    started_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.UTC))
    finished_at = Column(DateTime, nullable=True)
    state = Column(String, nullable=False)  # running | done | failed
    log = Column(Text, nullable=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=True)


class NotificationTarget(Base):
    __tablename__ = "notification_targets"
    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, nullable=False)
    config_json = Column(Text, default="{}")
    events_json = Column(Text, default='["all"]')
    enabled = Column(Boolean, default=True)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)


def get_setting(db: Session, key: str, default: str | None = None) -> str | None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))
    db.commit()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
