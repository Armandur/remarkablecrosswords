import datetime
import json
import logging
import traceback
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.config import ENABLE_SCHEDULER, REMARKABLE_FOLDER
from app.database import Crossword, Issue, Job, SessionLocal, Source, get_setting
from app.services.notifier import get_notifiers
from app.services.remarkable import get_remarkable_client
from app.services.sources import SOURCE_KINDS
from app.services.sources.base import ExternalIssue

logger = logging.getLogger(__name__)

def _get_remote_folder(db: Session, source: Source) -> str:
    base = get_setting(db, "remarkable_folder", REMARKABLE_FOLDER)
    if source.prefix:
        return str(Path(base) / source.prefix.lstrip("/"))
    return base

def sync_pending(db: Session):
    crosswords = db.query(Crossword).filter(Crossword.synced_at == None).all()
    if not crosswords:
        return False

    client = get_remarkable_client()
    if not client.check():
        logger.warning("Remarkable client check failed, skipping sync")
        return False

    any_synced = False
    for cw in crosswords:
        issue = db.query(Issue).filter(Issue.id == cw.issue_id).first()
        source = db.query(Source).filter(Source.id == issue.source_id).first()
        source_config = json.loads(source.config_json or "{}")
        overwrite = source_config.get("overwrite", False)

        remote_folder = _get_remote_folder(db, source)
        job = Job(kind='sync', state='running', source_id=source.id, issue_id=issue.id)
        db.add(job)
        db.commit()

        log_lines = [f"Korsord: {issue.name}", f"Mapp: {remote_folder}"]
        try:
            client.ensure_folder(remote_folder)

            remote_path = client.upload(Path(cw.pdf_path), remote_folder, overwrite=overwrite)
            log_lines.append(f"Uppladdad: {remote_path}")

            cw.synced_at = datetime.datetime.utcnow()
            cw.remarkable_path = remote_path
            job.state = 'done'
            job.finished_at = datetime.datetime.utcnow()
            job.log = "\n".join(log_lines)
            any_synced = True
        except Exception as e:
            log_lines.append(traceback.format_exc())
            job.state = 'failed'
            job.finished_at = datetime.datetime.utcnow()
            job.log = "\n".join(log_lines)
            logger.exception(f"Failed to sync crossword {cw.id}: {e}")

        db.commit()

    return any_synced

def sync_single_crossword(db: Session, crossword_id: int):
    cw = db.query(Crossword).filter(Crossword.id == crossword_id).first()
    if not cw:
        return False

    client = get_remarkable_client()
    if not client.check():
        return False

    issue = db.query(Issue).filter(Issue.id == cw.issue_id).first()
    source = db.query(Source).filter(Source.id == issue.source_id).first()
    source_config = json.loads(source.config_json or "{}")
    overwrite = source_config.get("overwrite", False)

    remote_folder = _get_remote_folder(db, source)
    job = Job(kind='sync', state='running', source_id=source.id, issue_id=issue.id)
    db.add(job)
    db.commit()

    log_lines = [f"Korsord: {issue.name}", f"Mapp: {remote_folder}"]
    success = False
    try:
        client.ensure_folder(remote_folder)

        if overwrite and cw.remarkable_path:
            try:
                client.rm(cw.remarkable_path)
                log_lines.append(f"Tog bort gammal fil: {cw.remarkable_path}")
            except Exception as rm_err:
                log_lines.append(f"Varning: kunde inte ta bort gammal fil: {rm_err}")

        remote_path = client.upload(Path(cw.pdf_path), remote_folder)
        log_lines.append(f"Uppladdad: {remote_path}")

        cw.synced_at = datetime.datetime.utcnow()
        cw.remarkable_path = remote_path
        job.state = 'done'
        job.finished_at = datetime.datetime.utcnow()
        job.log = "\n".join(log_lines)
        success = True
    except Exception as e:
        log_lines.append(traceback.format_exc())
        job.state = 'failed'
        job.finished_at = datetime.datetime.utcnow()
        job.log = "\n".join(log_lines)
        logger.exception(f"Failed to sync crossword {cw.id}: {e}")

    db.commit()
    return success

def run_sync_job(crossword_id: int, job_id: int):
    """Kör ett enskilt synk-jobb med en befintlig Job-post (skapad av route-handleren)."""
    db = SessionLocal()
    try:
        cw = db.query(Crossword).filter(Crossword.id == crossword_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()
        if not cw or not job:
            return

        client = get_remarkable_client()
        if not client.check():
            job.state = 'failed'
            job.finished_at = datetime.datetime.utcnow()
            job.log = "reMarkable client check misslyckades"
            db.commit()
            return

        issue = db.query(Issue).filter(Issue.id == cw.issue_id).first()
        source = db.query(Source).filter(Source.id == issue.source_id).first()
        source_config = json.loads(source.config_json or "{}")
        overwrite = source_config.get("overwrite", False)

        remote_folder = _get_remote_folder(db, source)
        log_lines = [f"Korsord: {issue.name}", f"Mapp: {remote_folder}"]

        try:
            client.ensure_folder(remote_folder)
            remote_path = client.upload(Path(cw.pdf_path), remote_folder, overwrite=overwrite)
            log_lines.append(f"Uppladdad: {remote_path}")

            cw.synced_at = datetime.datetime.utcnow()
            cw.remarkable_path = remote_path
            job.state = 'done'
            job.finished_at = datetime.datetime.utcnow()
            job.log = "\n".join(log_lines)
        except Exception as e:
            log_lines.append(traceback.format_exc())
            job.state = 'failed'
            job.finished_at = datetime.datetime.utcnow()
            job.log = "\n".join(log_lines)
            logger.exception(f"run_sync_job failed for crossword {crossword_id}: {e}")

        db.commit()
    except Exception as e:
        logger.exception(f"run_sync_job outer error: {e}")
    finally:
        db.close()

def run_pipeline_for_source(source_id: int):
    db = SessionLocal()
    try:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source or not source.enabled:
            return

        fetcher = SOURCE_KINDS.get(source.kind)
        if not fetcher:
            logger.error(f"Unknown source kind: {source.kind}")
            return

        available = fetcher.list_available(source)
        new_issues_count = 0
        
        for ext_issue in available:
            existing = db.query(Issue).filter(
                Issue.source_id == source.id,
                Issue.external_id == ext_issue.external_id
            ).first()
            
            if existing:
                continue

            job = Job(kind='download', state='running', source_id=source.id)
            db.add(job)
            db.commit()
            
            try:
                pdf_path = fetcher.download(source, ext_issue)
                
                issue = Issue(
                    source_id=source.id,
                    external_id=ext_issue.external_id,
                    name=ext_issue.name,
                    published_at=ext_issue.published_at,
                    pdf_path=str(pdf_path),
                    downloaded_at=datetime.datetime.utcnow(),
                    state='downloaded'
                )
                db.add(issue)
                db.flush() # get issue.id
                
                cw = Crossword(
                    issue_id=issue.id,
                    pdf_path=str(pdf_path),
                    extracted_at=datetime.datetime.utcnow()
                )
                db.add(cw)
                
                job.issue_id = issue.id
                job.state = 'done'
                job.finished_at = datetime.datetime.utcnow()
                new_issues_count += 1
            except Exception as e:
                job.state = 'failed'
                job.finished_at = datetime.datetime.utcnow()
                job.log = traceback.format_exc()
                logger.exception(f"Failed to download issue {ext_issue.external_id}: {e}")
            
            db.commit()

        synced = sync_pending(db)
        
        if synced:
            notifiers = get_notifiers(db)
            for n in notifiers:
                n.send(
                    title="Nya korsord synkade",
                    message=f"Synkade {new_issues_count} nya korsord till din reMarkable."
                )
                
    except Exception as e:
        logger.exception(f"Pipeline failed for source {source_id}: {e}")
    finally:
        db.close()

def rerender_issues_for_source(source_id: int):
    db = SessionLocal()
    try:
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            return

        fetcher = SOURCE_KINDS.get(source.kind)
        if not fetcher:
            logger.error(f"Unknown source kind: {source.kind}")
            return

        issues = db.query(Issue).filter(Issue.source_id == source_id).all()
        
        for issue in issues:
            job = Job(kind='rerender', state='running', source_id=source.id, issue_id=issue.id)
            db.add(job)
            db.commit()
            
            try:
                ext_issue = ExternalIssue(
                    external_id=issue.external_id,
                    name=issue.name,
                    published_at=issue.published_at
                )
                
                pdf_path = fetcher.download(source, ext_issue)
                
                issue.pdf_path = str(pdf_path)
                issue.downloaded_at = datetime.datetime.utcnow()
                issue.state = 'downloaded'
                
                cw = db.query(Crossword).filter(Crossword.issue_id == issue.id).first()
                if cw:
                    cw.pdf_path = str(pdf_path)
                    cw.synced_at = None
                    # remarkable_path behålls avsiktligt — används av sync om overwrite är aktiverat

                job.state = 'done'
                job.finished_at = datetime.datetime.utcnow()
                job.log = f"Renderade om: {issue.name}\nNy PDF: {pdf_path}"
            except Exception as e:
                job.state = 'failed'
                job.finished_at = datetime.datetime.utcnow()
                job.log = traceback.format_exc()
                logger.exception(f"Failed to rerender issue {issue.id}: {e}")
            
            db.commit()
            
    except Exception as e:
        logger.exception(f"Rerender failed for source {source_id}: {e}")
    finally:
        db.close()

def setup_scheduler(app=None):
    scheduler = BackgroundScheduler()
    if not ENABLE_SCHEDULER:
        logger.info("Scheduler is disabled via ENABLE_SCHEDULER")
        return scheduler

    db = SessionLocal()
    try:
        sources = db.query(Source).filter(Source.enabled == True, Source.schedule_cron != None).all()
        for source in sources:
            try:
                trigger = CronTrigger.from_crontab(source.schedule_cron)
                scheduler.add_job(
                    run_pipeline_for_source,
                    trigger=trigger,
                    args=[source.id],
                    id=f"source_{source.id}",
                    replace_existing=True
                )
                logger.info(f"Scheduled job for source {source.name} ({source.id}) with cron {source.schedule_cron}")
            except Exception as e:
                logger.error(f"Failed to schedule job for source {source.id}: {e}")
    finally:
        db.close()

    scheduler.start()
    return scheduler
