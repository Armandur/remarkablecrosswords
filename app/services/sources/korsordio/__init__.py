import json
import re
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from korsordio import fetch_competition_info, fetch_crossword, parse_name, render_pdf
from app.config import PDF_CROSSWORDS_DIR
from app.services.sources.base import ExternalIssue, SourceFetcher, render_filename

if TYPE_CHECKING:
    from app.database import Source

class KorsordioFetcher(SourceFetcher):
    def list_available(self, source: "Source") -> list[ExternalIssue]:
        config = json.loads(source.config_json)
        slug = config.get("slug")
        if not slug:
            return []

        url = f"https://app.korsord.io/g/{slug}/"
        try:
            with urllib.request.urlopen(url) as response:
                html = response.read().decode("utf-8")
        except Exception:
            return []

        pattern = rf"/c/({re.escape(slug)}-(\d+)-(\d+))/"
        matches = re.findall(pattern, html)

        issues = []
        seen_ids = set()
        for full_id, week, year in matches:
            ext_id = f"{week}-{year}"
            if ext_id not in seen_ids:
                issues.append(ExternalIssue(
                    external_id=ext_id,
                    name=full_id,
                    published_at=None
                ))
                seen_ids.add(ext_id)
            if len(issues) >= 4:
                break

        return issues

    def download(self, source: "Source", ext_issue: ExternalIssue) -> tuple[Path, list[str]]:
        config = json.loads(source.config_json)
        slug = config["slug"]
        sms_boxes = config.get("sms_boxes", True)
        fetch_competition = config.get("fetch_competition", True)

        match = re.match(r"(\d+)-(\d+)", ext_issue.external_id)
        if not match:
            raise ValueError(f"Invalid external_id: {ext_issue.external_id}")

        week = int(match.group(1))
        year = int(match.group(2))

        data = fetch_crossword(slug, week, year)
        meta = parse_name(data["name"])

        info = None
        if fetch_competition:
            try:
                info = fetch_competition_info(slug, week, year)
            except Exception:
                pass

        PDF_CROSSWORDS_DIR.mkdir(parents=True, exist_ok=True)
        if source.filename_template:
            filename = render_filename(source.filename_template, ext_issue, source.name)
            out_path = PDF_CROSSWORDS_DIR / f"{filename}.pdf"
        else:
            out_path = PDF_CROSSWORDS_DIR / (meta.slug() + ".pdf")

        render_pdf(data, out_path, sms_boxes=sms_boxes, competition_info=info)

        return out_path, []
