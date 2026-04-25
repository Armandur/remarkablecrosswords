from app.services.sources.korsordio import KorsordioFetcher
from app.services.sources.sr_melodikryss import SRMelodikryssFetcher

SOURCE_KINDS = {
    "korsordio": KorsordioFetcher(),
    "sr_melodikryss": SRMelodikryssFetcher(),
}
