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

class SourceFetcher(Protocol):
    def list_available(self, source: "Source") -> list[ExternalIssue]:
        ...

    def download(self, source: "Source", ext_issue: ExternalIssue) -> Path:
        ...
