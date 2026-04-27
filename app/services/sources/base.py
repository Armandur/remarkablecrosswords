import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from app.database import Source


class NoCrosswordError(Exception):
    """Kastas när ett nummer saknar korsord — förväntat läge, ej ett fel."""


@dataclass
class ExternalIssue:
    external_id: str
    name: str
    published_at: datetime | None

def render_filename(template: str, ext_issue: ExternalIssue, source_name: str) -> str:
    """Renderar ett filnamn utifrån ett template och saniterar det."""
    date_str = ext_issue.published_at.strftime("%Y-%m-%d") if ext_issue.published_at else ""
    year = str(ext_issue.published_at.year) if ext_issue.published_at else ""
    month = f"{ext_issue.published_at.month:02d}" if ext_issue.published_at else ""
    day = f"{ext_issue.published_at.day:02d}" if ext_issue.published_at else ""
    
    try:
        filename = template.format(
            name=ext_issue.name,
            date=date_str,
            year=year,
            month=month,
            day=day,
            source=source_name,
            id=ext_issue.external_id
        )
    except (KeyError, ValueError, AttributeError):
        # Fallback om templaten är ogiltig
        filename = f"{source_name}-{ext_issue.external_id}"
        
    # Sananitering: ta bort < > : " / \ | ? * och kontrolltecken (ASCII 0–31)
    filename = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)
    # Trimma separatortecken i kanterna (uppstår när variabler som {date} är tomma)
    filename = filename.strip(' .-_–—')
    
    if not filename:
        filename = f"{source_name}-{ext_issue.external_id}"
        
    return filename

class SourceFetcher(Protocol):
    def list_available(self, source: "Source") -> list[ExternalIssue]:
        ...

    def download(self, source: "Source", ext_issue: ExternalIssue) -> tuple[Path, list[str]]:
        ...
