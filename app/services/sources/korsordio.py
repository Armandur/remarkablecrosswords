import json
import re
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from korsordio import fetch_competition_info, fetch_crossword, parse_name, render_pdf
from app.config import PDF_CROSSWORDS_DIR
from app.services.sources.base import ExternalIssue, SourceFetcher

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

        # Pattern: /c/sverigekrysset-17-26/
        pattern = rf"/c/({re.escape(slug)}-(\d+)-(\d+))/"
        matches = re.findall(pattern, html)
        
        issues = []
        # matches are (full_match, week, year)
        # We want the 4 latest. matches usually come in order of appearance in HTML.
        # Let's just take the first 4 if they look like links.
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

    def download(self, source: "Source", ext_issue: ExternalIssue) -> Path:
        config = json.loads(source.config_json)
        slug = config["slug"]
        
        # ext_issue.external_id is 'v-yy'
        match = re.match(r"(\d+)-(\d+)", ext_issue.external_id)
        if not match:
            raise ValueError(f"Invalid external_id: {ext_issue.external_id}")
        
        week = int(match.group(1))
        year = int(match.group(2))
        
        data = fetch_crossword(slug, week, year)
        meta = parse_name(data["name"])
        
        info = None
        try:
            info = fetch_competition_info(slug, week, year)
        except Exception:
            pass # optional
            
        PDF_CROSSWORDS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = PDF_CROSSWORDS_DIR / (meta.slug() + ".pdf")
        
        render_pdf(data, out_path, sms_boxes=True, competition_info=info)
        
        return out_path
