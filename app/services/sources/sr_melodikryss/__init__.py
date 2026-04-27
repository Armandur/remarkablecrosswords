import datetime
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import PDF_CROSSWORDS_DIR
from app.services.sources.base import ExternalIssue, SourceFetcher, render_filename

if TYPE_CHECKING:
    from app.database import Source

_URL = "https://sr.korsord.se/images/kryss/kryss{year}w{week}.pdf"


def _week_dates(n: int) -> list[datetime.date]:
    today = datetime.date.today()
    return [today - datetime.timedelta(weeks=i) for i in range(n)]


class SRMelodikryssFetcher(SourceFetcher):
    def list_available(self, source: "Source") -> list[ExternalIssue]:
        issues = []
        seen: set[str] = set()
        for d in _week_dates(8):
            iso = d.isocalendar()
            year, week = iso[0], iso[1]
            ext_id = f"{year}w{week}"
            if ext_id in seen:
                continue
            seen.add(ext_id)
            url = _URL.format(year=year, week=week)
            try:
                req = urllib.request.Request(url, method="HEAD")
                with urllib.request.urlopen(req, timeout=10) as r:
                    ct = r.headers.get("Content-Type", "")
                    if r.status == 200 and "pdf" in ct:
                        pub = datetime.datetime(year, d.month, d.day)
                        issues.append(ExternalIssue(
                            external_id=ext_id,
                            name=f"SR Melodikryss {year} v.{week}",
                            published_at=pub,
                        ))
                        if len(issues) == 4:
                            break
            except Exception:
                pass
        return issues

    def download(self, source: "Source", ext_issue: ExternalIssue) -> tuple[Path, list[str]]:
        year, week = ext_issue.external_id.split("w")
        url = _URL.format(year=int(year), week=int(week))
        PDF_CROSSWORDS_DIR.mkdir(parents=True, exist_ok=True)
        
        if source.filename_template:
            filename = render_filename(source.filename_template, ext_issue, source.name)
            out_path = PDF_CROSSWORDS_DIR / f"{filename}.pdf"
        else:
            out_path = PDF_CROSSWORDS_DIR / f"sr-melodikryss-{ext_issue.external_id}.pdf"

        with urllib.request.urlopen(url, timeout=30) as r:
            out_path.write_bytes(r.read())
        return out_path, []
