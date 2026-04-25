from app.services.sources.korsordio import KorsordioFetcher
from app.services.sources.sr_melodikryss import SRMelodikryssFetcher
from app.services.sources.prenly import PrenlyFetcher
from app.services.sources.yippie_harnosand import YippieHarnosandFetcher

SOURCE_KINDS = {
    "korsordio": KorsordioFetcher(),
    "sr_melodikryss": SRMelodikryssFetcher(),
    "prenly": PrenlyFetcher(),
    "yippie_harnosand": YippieHarnosandFetcher(),
}
