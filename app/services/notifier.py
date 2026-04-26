import base64
import json
import logging
import urllib.request
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.database import NotificationTarget

logger = logging.getLogger(__name__)

NOTIFICATION_EVENTS = {
    "download_ok": "Nedladdning lyckad",
    "download_fail": "Nedladdning misslyckad",
    "sync_ok": "Synk lyckad",
    "sync_fail": "Synk misslyckad",
}

class Notifier(Protocol):
    def send(self, title: str, message: str, click_url: str | None = None) -> bool:
        ...

class NtfyNotifier:
    def __init__(self, config: dict):
        if "url" in config and "topic" not in config:
            self.url = config["url"]
        else:
            server = config.get("server", "https://ntfy.sh").rstrip("/")
            topic = config.get("topic", "")
            self.url = f"{server}/{topic}"
        self.auth_type = config.get("auth_type", "none")
        self.token = config.get("token", "")
        self.username = config.get("username", "")
        self.password = config.get("password", "")

    def send(self, title: str, message: str, click_url: str | None = None) -> bool:
        try:
            headers = {"Title": title.encode("utf-8")}
            if click_url:
                headers["Click"] = click_url
            if self.auth_type == "token" and self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            elif self.auth_type == "password" and self.username:
                creds = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
                headers["Authorization"] = f"Basic {creds}"
            req = urllib.request.Request(self.url, data=message.encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req) as resp:
                return resp.status == 200
        except Exception as e:
            logger.exception(f"Failed to send ntfy notification to {self.url}: {e}")
            return False

def build_notifier(target: "NotificationTarget") -> "Notifier | None":
    config = json.loads(target.config_json)
    if target.kind == "ntfy":
        return NtfyNotifier(config)
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
