"""The report's figures, rendered as inline SVG.

SVG rather than a raster, because the report is read on a shared screen in a
meeting and a line chart at someone else's zoom level should stay a line rather
than becoming pixels. Inline rather than linked, because the report is one file
that has to open from a download with nothing beside it.

Ink is emitted as `currentColor` so the figures take the page's text colour
instead of carrying a baked-in one, which is what lets the same file read in a
light and a dark theme. Matplotlib has no notion of that, so every axis, tick,
label and gridline is drawn in one sentinel colour and the sentinel is swapped
for `currentColor` on the way out. Opacity survives the swap, which is what
keeps the grid recessive.

No figure here carries two y-axes. Where two measures of different scale belong
side by side they are drawn as two panels sharing an x-axis instead, since a
second scale lets a chart imply any relationship the author likes by choosing
where the axes cross.
"""

import re
from datetime import date, timedelta
from io import StringIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

# Every mark that is not data. Swapped for `currentColor` on the way out, so the
# figures inherit the page's ink and theme with it.
INK = "#010203"

# Categorical slots 1-3 from the validated reference palette, used here only as
# sentinels: each is swapped for a CSS variable on the way out, so one rendering
# of a figure serves both themes and the dark steps are a selected palette in
# the page's stylesheet rather than an automatic lightening of these. Three is
# the cap, being what clears every all-pairs gate in both modes; a fourth would
# put yellow beside orange and fail them.
SERIES = ("#2a78d6", "#eb6834", "#1baf7a")

plt.rcParams.update(
    {
        # Text stays text rather than becoming outlines, so it inherits the
        # page's font stack and the file stays small enough to inline.
        "svg.fonttype": "none",
        "font.size": 9,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "text.color": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def _svg(fig) -> str:
    """The figure as an inline SVG fragment, themed to the page's ink."""
    buffer = StringIO()
    fig.savefig(buffer, format="svg", transparent=True, bbox_inches="tight")
    plt.close(fig)
    markup = buffer.getvalue()
    markup = markup[markup.index("<svg") :]
    markup = re.sub(re.escape(INK), "currentColor", markup, flags=re.IGNORECASE)
    for slot, colour in enumerate(SERIES, start=1):
        markup = re.sub(re.escape(colour), f"var(--series-{slot})", markup, flags=re.IGNORECASE)
    # A fixed pixel width would overflow a narrow screen; the viewBox already
    # carries the aspect ratio, so let the container decide the width.
    return re.sub(r'<svg width="[^"]*" height="[^"]*"', "<svg", markup, count=1)


def _days(rows: list[dict], key: str = "week") -> list[date]:
    return [date.fromisoformat(row[key]) for row in rows]


def _visible(days: list[date], events: list[dict]) -> list[tuple[date, str]]:
    """The events that fall inside the reported span, dated and named.

    A week runs to the Sunday after its Monday, so an event late in the last
    reported week sits days past the final data point and still belongs on the
    chart.
    """
    if not days:
        return []
    limit = max(days) + timedelta(days=6)
    marks = [(date.fromisoformat(e["date"]), e["label"]) for e in events]
    return sorted((when, label) for when, label in marks if min(days) <= when <= limit)


def _frame(ax, days: list[date], events: list[dict], ylabel: str) -> None:
    """The furniture every panel shares: recessive grid, dates, event marks."""
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color=INK, alpha=0.12, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO, interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    marks = _visible(days, events)
    if days:
        # Room on the right for the series labels, and for an event that lands
        # after the last data point without being drawn off the axis.
        right = max([max(days)] + [when for when, _ in marks])
        ax.set_xlim(min(days) - timedelta(days=4), right + timedelta(days=4))
    for when, _ in marks:
        ax.axvline(when, color=INK, alpha=0.35, linewidth=1, linestyle=(0, (4, 3)))


def _label_events(ax, days: list[date], events: list[dict]) -> None:
    """Event names, once per figure, along the top of its first panel.

    Set to the left of their own line, because the right of the panel is where
    the series name their last point and the two would otherwise sit on top of
    each other.
    """
    for when, label in _visible(days, events):
        ax.annotate(
            label,
            xy=(when, 1),
            xycoords=("data", "axes fraction"),
            xytext=(-4, -3),
            textcoords="offset points",
            rotation=90,
            va="top",
            ha="right",
            fontsize=7,
            alpha=0.7,
        )


# How far apart two labels past the right spine have to sit, in axes fractions,
# before one is on top of the other.
_LABEL_GAP = 0.075


def _end_labels(ax, labelled: list[tuple[float, str, str]]) -> None:
    """The series named past the right spine, level with their own last values.

    Outside the axis rather than beside the point, because the last weeks are
    where the event marks land and a label on the data would be on them too.
    Two series ending at the same value would print one label over the other, so
    they are pushed apart in the order their values put them: a legend alone
    would leave identity to colour, which is exactly what a direct label is for.
    """
    bottom, top = ax.get_ylim()
    span = top - bottom or 1
    placed: list[tuple[float, str, str]] = []
    for value, text, colour in sorted(labelled):
        spot = (value - bottom) / span
        if placed and spot - placed[-1][0] < _LABEL_GAP:
            spot = placed[-1][0] + _LABEL_GAP
        placed.append((spot, text, colour))
    for spot, text, colour in placed:
        ax.annotate(
            text,
            xy=(1, spot),
            xycoords="axes fraction",
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            ha="left",
            fontsize=8,
            color=colour,
            fontweight="bold",
            annotation_clip=False,
        )


def _legend(ax, columns: int) -> None:
    """The key, above the plot rather than inside it, where no data can be under it."""
    ax.legend(
        frameon=False,
        fontsize=8,
        ncol=columns,
        loc="lower left",
        bbox_to_anchor=(0, 1.0),
        borderaxespad=0.2,
        handlelength=1.6,
        columnspacing=1.6,
    )


def presence(weeks: list[dict], events: list[dict]) -> str:
    """How much of the published field the deck holds, week by week.

    Two panels rather than two axes. The challenge stratum is read as a share
    because the number of events a week runs is the calendar's decision and not
    the deck's, and the league stratum is read as a raw count because that is
    what a trophy dump is: every 5-0 published, one pilot's repeats included,
    since what the panel measures is how much of that stratum the deck occupies.
    """
    series = SERIES[0]
    days = _days(weeks)
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(9, 4.4), sharex=True, gridspec_kw={"hspace": 0.18}
    )

    shares = [(row["chal_share"] or 0) * 100 for row in weeks]
    top.plot(days, shares, color=series, linewidth=2, marker="o", markersize=4)
    top.set_title("Share of published top-32 slots", loc="left", fontsize=10, pad=14)
    _frame(top, days, events, "% of top 32")
    _label_events(top, days, events)
    _end_labels(top, [(shares[-1], f"{shares[-1]:.1f}%", series)])

    trophies = [row["trophies"] for row in weeks]
    bottom.bar(days, trophies, width=5, color=series, linewidth=0)
    bottom.set_title("League trophies, uncapped", loc="left", fontsize=10, pad=6)
    _frame(bottom, days, events, "5-0 lists")
    _end_labels(bottom, [(trophies[-1], str(trophies[-1]), series)])
    return _svg(fig)


def conversion(weeks: list[dict], events: list[dict]) -> str:
    """Whether presence turns into finishes.

    Both series are shares of a published stratum, so they sit on one axis and
    the gap between them is the reading: a deck above its own presence line is
    finishing better than its numbers alone would put it. Placement is not
    averaged anywhere here. An average over the top 32 rewards a week the deck
    barely turned up to, since one list finishing first beats eight lists
    spread through the cut, and it is truncated at 32 besides.
    """
    first, second = SERIES[:2]
    days = _days(weeks)
    fig, ax = plt.subplots(figsize=(9, 3.2))

    presence_pct = [(row["chal_share"] or 0) * 100 for row in weeks]
    top8_pct = [(row["top8_share"] or 0) * 100 for row in weeks]
    ax.plot(days, presence_pct, color=first, linewidth=2, marker="o", markersize=4,
            label="Share of top 32")
    ax.plot(days, top8_pct, color=second, linewidth=2, marker="o", markersize=4,
            label="Share of top 8")
    ax.set_title("Conversion: top-8 share against top-32 share",
                 loc="left", fontsize=10, pad=24)
    _frame(ax, days, events, "% of published slots")
    _label_events(ax, days, events)
    _end_labels(ax, [(presence_pct[-1], "top 32", first), (top8_pct[-1], "top 8", second)])
    _legend(ax, 2)
    return _svg(fig)


def copy_drift(rows: list[dict], events: list[dict]) -> str:
    """The counts the deck argues about, as a mean over the lists that run them.

    The mode is not used and should not be: on these cards it oscillates every
    other week and every oscillation reverses, because a plurality one pilot can
    flip is holding it. The mean moves where the mode only flickers, and on this
    deck it is the only place adaptation is visible at all, every one of these
    cards sitting at an adoption no share reading will ever move.
    """
    palette = SERIES
    cards = sorted({row["card"] for row in rows})
    fig, ax = plt.subplots(figsize=(9, 3.4))
    days: list[date] = []
    labelled = []
    for slot, card in enumerate(cards):
        points = [row for row in rows if row["card"] == card]
        card_days, means = _days(points), [row["mean_copies"] for row in points]
        days = days or card_days
        colour = palette[slot % len(palette)]
        ax.plot(card_days, means, color=colour, linewidth=2, marker="o", markersize=4, label=card)
        labelled.append((means[-1], f"{means[-1]:.1f}", colour))
    ax.set_title("Copies run, mean over the lists playing the card",
                 loc="left", fontsize=10, pad=24)
    _frame(ax, days, events, "mean copies")
    _label_events(ax, days, events)
    _end_labels(ax, labelled)
    _legend(ax, 3)
    return _svg(fig)


def stability(rows: list[dict], events: list[dict]) -> str:
    """How much of a week is last week's most-played list, registered again.

    High is not good and not bad, it is settled: a week that is mostly one 75
    copied is a week the deck stopped being built. It is also the warning that
    such a week is not the sample its list count claims, since the evidence in
    it is closer to its distinct builds than to its lists.
    """
    series = SERIES[0]
    days = _days(rows)
    shares = [(row["copied_share"] or 0) * 100 for row in rows]
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.bar(days, shares, width=5, color=series, linewidth=0)
    ax.set_title("Stability: share of the week identical to last week's most-played list",
                 loc="left", fontsize=10, pad=14)
    _frame(ax, days, events, "% of lists")
    _label_events(ax, days, events)
    return _svg(fig)
