"""The outcome contrast at the seam the rest of the pipeline is tested at.

The instrument answers whether the lists carrying a configuration are
distributed differently across the published bands than the same camp's lists
without it. What has to hold is that it separates a real difference, refuses to
call one it could not have seen, and says which of the two it did.

The series are written rather than captured, for the reason `tests/synthetic.py`
gives: a contrast needs both bands populated in a known proportion, and the
captured days hold whatever the field happened to do.
"""

from deck_engine import outcome, store
from tests import synthetic
from tests.synthetic import challenge, entry, league

CAMP = "non-fallaji"
CARD = "Kavaero, Mind-Bitten"


def _built(tmp_path, events):
    db = tmp_path / "engine.duckdb"
    store.build(synthetic.write_cache(tmp_path / "raw", events), db)
    return db


def _ranked(day, event_id, carried, band_of):
    """A thirty-two list challenge, each seat placed where `band_of` puts it.

    `carried` names the seats registering the configuration. Points fall with
    placement so the standings are ordered as a real event's are, though nothing
    here reads them: the contrast is drawn on the band and never on the points.
    """
    return challenge(
        day,
        [
            entry(
                f"seat{seat}",
                CAMP,
                {CARD: (1, 0)} if seat in carried else None,
                points=max(3, 21 - band_of(seat) // 2),
                placement=band_of(seat),
            )
            for seat in range(32)
        ],
        event_id=event_id,
    )


def test_a_configuration_the_bands_genuinely_separate_is_called(tmp_path):
    """The reading the instrument exists to make, in the one case it can make it.

    Fourteen of the sixteen lists registering the card finished above the cut and
    two of the sixteen without it did. That is a difference no plausible shuffle
    of thirty-two lists produces, so the contrast calls it rather than leaving it
    as noise, and it is called on the band and not on the Swiss points: every one
    of these lists finished, and the points they finished on are bunched.
    """
    # Seats 0-15 carry the card. Fourteen of them are placed in the top 16 and
    # the other two below it; the sixteen without it are placed the other way up.
    top = set(range(14)) | {16, 17}
    db = _built(
        tmp_path,
        [
            _ranked(
                "2026-08-05",
                "12846100",
                set(range(16)),
                lambda s: 1 + sorted(top).index(s) if s in top else 17 + s % 16,
            )
        ],
    )

    read = outcome.contrast(CARD, db_path=db, camp=CAMP)

    assert read["with_lists"] == 16 and read["without_lists"] == 16
    assert read["with_made_band"] == 14 and read["without_made_band"] == 2
    assert read["difference"] > 0.7
    assert read["p"] < outcome.ALPHA
    assert read["state"] == outcome.SEPARATES


def test_a_difference_the_contrast_could_not_have_seen_is_a_null_that_says_so(tmp_path):
    """A null is only as strong as the difference it could have caught.

    Half of each arm above the cut is no difference at all, and the reading has
    to come back saying so. What it must also carry is the floor: at sixteen
    lists a side the contrast cannot see anything short of a landslide, so a
    reader handed the p-value alone would take "no difference found" for "no
    difference", which is the error this instrument is most likely to cause.
    """
    even = {seat for seat in range(32) if seat % 2 == 0}
    db = _built(
        tmp_path,
        [_ranked("2026-08-05", "12846101", even, lambda s: 1 + s)],
    )

    read = outcome.contrast(CARD, db_path=db, camp=CAMP)

    assert read["with_made_band"] == read["without_made_band"] == 8
    assert read["difference"] == 0
    assert read["state"] == outcome.UNDETECTABLE
    # Nothing under a landslide would have been called on a population this size.
    assert read["floor"] > 0.3


def test_the_league_conversion_is_capped_at_one_list_per_pilot(tmp_path):
    """A dump is published without dedup, so a gap has to survive the grinder.

    One pilot trophying four times on his pet configuration is one pilot's
    preference, and uncapped it would report the whole league stratum as having
    converted on it. The published gap counts each pilot once, the publication
    count stays beside it, and the row says what the cap did.
    """
    dump = league(
        "2026-08-05",
        # Zeect trophies four times on the card; three other pilots trophy once
        # each without it. Counted by list the card holds four of seven; counted
        # by pilot, one of four.
        [entry("Zeect", CAMP, {CARD: (1, 0)}) for _ in range(4)]
        + [entry(f"other{seat}", CAMP) for seat in range(3)],
    )
    db = _built(tmp_path, [dump, _ranked("2026-08-04", "12846102", set(), lambda s: 1 + s)])

    conversion = outcome.contrast(CARD, db_path=db, camp=CAMP)["conversion"]

    assert conversion["league"]["lists"] == 7, "the cache stays exactly as published"
    assert conversion["league"]["uncapped"] == 4 / 7
    assert conversion["league"]["share"] == 1 / 4, "and the reading counts the pilot once"
    assert conversion["cap_effect"] == "collapses"
