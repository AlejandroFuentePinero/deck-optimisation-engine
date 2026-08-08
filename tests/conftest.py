"""What the whole suite is pointed at before any test names anything.

The raw cache and the reference list are named by every test that reads them,
because there is one of each and a fixture directory sits beside it. The meta
history is the exception: it is a directory the pilot appends to as routine
work, and it was reachable by any call that left `meta_dir` out. Fifty-odd
builds did, so the committed history was a silent input to most of the suite,
and the two tests that read it deliberately were pinned to its length. They
broke the first time a second screenshot was transcribed, which is the pilot
doing his job.

So the default is redirected here, once, to a frozen snapshot. A test that
wants the live history names it, which is what makes reading it a decision. The
readings then answer to the code rather than to how many screenshots have been
taken.
"""

from pathlib import Path

import pytest

from deck_engine import config

FIXTURE_META = Path(__file__).parent / "fixtures" / "meta"


@pytest.fixture(autouse=True)
def frozen_meta_history():
    """Point the unnamed meta history at the frozen snapshot, for every test.

    Set on the config rather than on each function's default, which is why those
    defaults are resolved at the call: bound at import there is nothing here
    could reach them, and every call site would have to remember instead.

    On a context of its own rather than the `monkeypatch` fixture, which a test
    taking that fixture shares with this one: a test that undoes its own patch
    part way through would undo this with it and silently get the live history
    back for the rest of the run.
    """
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(config, "META_DIR", FIXTURE_META)
        yield
