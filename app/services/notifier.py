import json
import logging
import urllib.request
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from app.database import NotificationTarget

logger = logging.getLogger(__name__)

class Notifier(Protocol):
    def send(self, title: str, message: str, click_url: str | None = None) -> bool:
        ...

class NtfyNotifier:
    def __init__(self, url: str):
        self.url = url

    def send(self, title: str, message: str, click_url: str | None = None) -> bool:
        try:
            headers = {"Title": title.encode("utf-8")}
            if click_url:
                headers["Click"] = click_url
            
            req = urllib.request.Request(self.url, data=message.encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req) as response:
                return response.status == 200
        except Exception as e:
            logger.exception(f"Failed to send ntfy notification to {self.url}: {e}")
            return False

def get_notifiers(db: "Session") -> list[Notifier]:
    from app.database import NotificationTarget
    targets = db.query(NotificationTarget).filter(NotificationTarget.enabled == True).all()
    
    notifiers = []
    for target in targets:
        config = json.loads(target.config_json)
        if target.kind == 'ntfy':
            url = config.get('url')
            if url:
                notifiers.append(NtfyNotifier(url))
        else:
            logger.warning(f"Unknown notification target kind: {target.kind}")
            
    return notifiers
