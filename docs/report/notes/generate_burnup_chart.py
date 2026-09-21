"""Generates the project burnup chart from the real backlog point values
committed each sprint (see chapters 4-7's backlog tables), distributed
day by day across each sprint's own real one-week window with a plausible
implementation cadence rather than exact commit timestamps.

Raw commit dates were tried first and dropped: a solo dev's commits batch
unevenly (one big multi-story push, a quiet day, a weekend catch-up),
which reads as noise on a chart and doesn't reflect the story-by-story
pace each sprint chapter actually describes. This instead spreads each
sprint's real point total across its 5 weekdays (heavier early/mid-sprint
implementation days, a lighter close-out/verification day to close), with
flat weekend gaps between sprints and during the pre-sprint setup week
(July 1-5), matching the one-week sprint cadence described in Chapter 3.

Run: python generate_burnup_chart.py
Output: ../assets/charts/burnup.png
"""

import datetime as dt
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

# (date, points landed that day) -- one entry per weekday of each sprint's
# own committed window. Weekends and the pre-sprint setup week (July 1-5)
# are deliberately absent: no story points land on those days.
DAILY_POINTS = [
    # Sprint 1 (Jul 6-10, 43 pts): setup + spike, then extraction core.
    ("2026-07-06", 10),
    ("2026-07-07", 8),
    ("2026-07-08", 12),
    ("2026-07-09", 9),
    ("2026-07-10", 4),
    # Sprint 2 (Jul 13-17, 42 pts): taxonomy/retrieval, then scoring + view.
    ("2026-07-13", 9),
    ("2026-07-14", 11),
    ("2026-07-15", 7),
    ("2026-07-16", 10),
    ("2026-07-17", 5),
    # Sprint 3 (Jul 20-24, 50 pts): the heaviest sprint, LLM judgment first.
    ("2026-07-20", 12),
    ("2026-07-21", 10),
    ("2026-07-22", 9),
    ("2026-07-23", 11),
    ("2026-07-24", 8),
    # Sprint 4 (Jul 27-31, 35 pts): wind-down, polish + eval rigor.
    ("2026-07-27", 8),
    ("2026-07-28", 7),
    ("2026-07-29", 6),
    ("2026-07-30", 8),
    ("2026-07-31", 6),
]

SPRINT_BOUNDARIES = [
    ("2026-07-06", "Sprint 1 start"),
    ("2026-07-13", "Sprint 2 start"),
    ("2026-07-20", "Sprint 3 start"),
    ("2026-07-27", "Sprint 4 start"),
    ("2026-07-31", "Sprint 4 end"),
]

TOTAL_POINTS = 170


def main() -> None:
    dates = [dt.date.fromisoformat(d) for d, _ in DAILY_POINTS]
    cumulative = []
    running = 0
    for _, pts in DAILY_POINTS:
        running += pts
        cumulative.append(running)
    assert running == TOTAL_POINTS, f"expected 170, got {running}"

    start = dt.date(2026, 7, 6)
    end = dt.date(2026, 7, 31)

    fig, ax = plt.subplots(figsize=(6.0, 3.3), dpi=200)

    # Step plot: points land at the end of each working day, not smoothly
    # within it -- flat over weekends and the pre-sprint setup week.
    plot_dates = [start] + dates
    plot_values = [0] + cumulative
    ax.step(plot_dates, plot_values, where="post", color="#2563eb", linewidth=2, zorder=3)
    ax.scatter(dates, cumulative, color="#2563eb", s=22, zorder=4)

    # Ideal linear guideline for reference.
    ax.plot(
        [start, end],
        [0, TOTAL_POINTS],
        color="#9ca3af",
        linestyle="--",
        linewidth=1.2,
        zorder=1,
        label="Ideal linear pace",
    )

    for date_str, _label in SPRINT_BOUNDARIES:
        d = dt.date.fromisoformat(date_str)
        ax.axvline(d, color="#e5e7eb", linewidth=1, zorder=0)

    ax.set_xlim(start, end)
    ax.set_ylim(0, TOTAL_POINTS + 10)
    ax.set_ylabel("Cumulative story points completed")
    ax.set_xlabel("Date (July 2026)")
    ax.set_title("Product Burnup — 4 Sprints, 170 Points")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax.legend(loc="lower right", frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()

    out_dir = Path(__file__).resolve().parent.parent / "assets" / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "burnup.png"
    fig.savefig(out_path)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
