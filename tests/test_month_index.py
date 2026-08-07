"""When a month index the site will not serve is fatal, and when it is not.

The network layer itself stays out of the test seam (see the PRD's Testing
Decisions) and is verified against the live site. What is under test here is
the one decision around it that is calendar, not network: which month is
allowed to have no index yet. `_get` is stood in for so that decision can be
observed without the site.
"""

import pytest

from deck_engine import mtgo


def _site(*published):
    """The site's month indexes: the months named list one event, the rest fail."""

    def get(url, usable):
        year, month = (int(part) for part in url.split("/decklists/")[1].split("/"))
        if (year, month) not in published:
            raise mtgo.Unavailable(url)
        return f'<a href="/decklist/modern-league-{year}-{month:02d}-0512345678">'

    return get


def test_a_month_the_site_has_not_opened_yet_is_empty_rather_than_missing(monkeypatch):
    """Melbourne turns the month over some fourteen hours before MTGO does.

    So a run in that window asks for a month index the site has published
    nothing into, and must cache what the months behind it hold rather than
    lose the run to a page that does not exist yet.
    """
    monkeypatch.setattr(mtgo, "_get", _site((2026, 7), (2026, 8)))

    slugs = mtgo.event_slugs("2026-07-01", "modern", "2026-09-01", today="2026-09-01")

    assert slugs == [
        "modern-league-2026-07-0512345678",
        "modern-league-2026-08-0512345678",
    ]


def test_the_current_month_is_only_allowed_to_be_absent_on_its_first_day(monkeypatch):
    """Past the first, the month has events in it and its index exists.

    An index that will not load then is the site stubbing, which is common and
    does not reliably clear within the retries. Reading that as an empty month
    would no-op the run on a bad afternoon instead of caching what published.
    """
    monkeypatch.setattr(mtgo, "_get", _site((2026, 7), (2026, 8)))

    with pytest.raises(mtgo.Unavailable, match="2026/09"):
        mtgo.event_slugs("2026-07-01", "modern", "2026-09-02", today="2026-09-02")


def test_a_month_behind_the_current_one_failing_to_serve_ends_the_run(monkeypatch):
    """A month the site published long ago is never legitimately absent.

    Tolerating the month that has not opened yet must not extend to the range
    behind it, or a run would rebuild the store off a fraction of the history
    and say nothing about the rest.
    """
    monkeypatch.setattr(mtgo, "_get", _site((2026, 8)))

    with pytest.raises(mtgo.Unavailable, match="2026/07"):
        mtgo.event_slugs("2026-07-01", "modern", "2026-09-01", today="2026-09-01")
