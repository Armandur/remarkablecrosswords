"""Tolka korsord.io:s `name`-fält till läsbar metadata.

Format: ``<PREFIX>_<YYMMDD>$<intern-id>``, t.ex. ``SK_260420$5067``.
Prefixet identifierar titeln (SK_=Sverigekrysset, MK_=Miljonkrysset)
och YYMMDD är publiceringsdatumet. ISO-veckan beräknas från datumet.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

TITLE_PREFIXES = {
    "SK_": "Sverigekrysset",
    "MK_": "Miljonkrysset",
}


@dataclass(frozen=True)
class CrosswordMeta:
    title: str                 # t.ex. "Sverigekrysset"
    name: str                  # rådata, t.ex. "SK_260420$5067"
    published: date            # publiceringsdatum
    iso_year: int              # ISO-år
    iso_week: int              # ISO-vecka
    competition_number: int    # tävlingsnummer (samma som $-delen i name)

    def display_title(self) -> str:
        """Mänskligt läsbar rubrik."""
        return (
            f"{self.title} {self.iso_year}v{self.iso_week}, "
            f"publicerat {self.published.isoformat()}, "
            f"tävlingsnr {self.competition_number}"
        )

    def slug(self) -> str:
        """Filnamns-slug med år före vecka för korrekt sortering.

        Format: ``<titel-i-lowercase-med-bindestreck>-<år>-w<vv>``,
        t.ex. ``sverigekrysset-2026-w17``.
        """
        title_slug = self.title.lower().replace(" ", "-")
        return f"{title_slug}-{self.iso_year}-w{self.iso_week:02d}"


def parse_name(name: str) -> CrosswordMeta:
    """Parse ``name``-fältet till CrosswordMeta.

    Kastar ValueError om formatet inte känns igen.
    """
    if "_" not in name or "$" not in name:
        raise ValueError(f"Unexpected crossword name format: {name!r}")
    prefix_part, rest = name.split("_", 1)
    prefix = prefix_part + "_"
    yymmdd, comp_str = rest.split("$", 1)
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        raise ValueError(f"Unexpected date in name: {name!r}")
    if not comp_str.isdigit():
        raise ValueError(f"Unexpected competition number in name: {name!r}")
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    pub = date(2000 + yy, mm, dd)
    iso_year, iso_week, _ = pub.isocalendar()
    title = TITLE_PREFIXES.get(prefix, prefix.rstrip("_"))
    return CrosswordMeta(
        title=title,
        name=name,
        published=pub,
        iso_year=iso_year,
        iso_week=iso_week,
        competition_number=int(comp_str),
    )
