import json
import logging
from typing import TYPE_CHECKING
from .ntfy import NtfyNotifier
from .base import Notifier

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.database import NotificationTarget

logger = logging.getLogger(__name__)

NOTIFIER_KINDS: dict[str, type[Notifier]] = {
    NtfyNotifier.KIND: NtfyNotifier,
}

NOTIFICATION_EVENTS = {
    "download_ok": "Nedladdning lyckad",
    "download_fail": "Nedladdning misslyckad",
    "sync_ok": "Synk lyckad",
    "sync_fail": "Synk misslyckad",
}

TEST_MESSAGES = {
    "download_ok": {
        "title": "Nedladdning lyckad",
        "message": "[TEST] Testblad v.17 (2026-04-26) har laddats ned.",
    },
    "download_fail": {
        "title": "Nedladdning misslyckades",
        "message": "[TEST] Kunde inte ladda ned Testblad v.17.",
    },
    "sync_ok": {
        "title": "Synk lyckad",
        "message": "[TEST] Testblad v.17 har synkats till reMarkable.",
    },
    "sync_fail": {
        "title": "Synk misslyckades",
        "message": "[TEST] Kunde inte synka Testblad v.17 till reMarkable.",
    },
}

def build_notifier(target: "NotificationTarget") -> Notifier | None:
    try:
        config = json.loads(target.config_json)
    except Exception:
        config = {}
        
    notifier_class = NOTIFIER_KINDS.get(target.kind)
    if notifier_class:
        return notifier_class(config)
        
    logger.warning(f"Unknown notification target kind: {target.kind}")
    return None

def get_notifiers(db: "Session", event: str | None = None) -> list[Notifier]:
    from app.database import NotificationTarget
    targets = db.query(NotificationTarget).filter(NotificationTarget.enabled == True).all()
    notifiers = []
    for target in targets:
        if event:
            try:
                events = json.loads(target.events_json or '["all"]')
            except Exception:
                events = ["all"]
            if "all" not in events and event not in events:
                continue
        notifier = build_notifier(target)
        if notifier:
            notifiers.append(notifier)
    return notifiers
