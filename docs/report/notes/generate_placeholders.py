"""Temporary placeholder images for the 3 Sprint 4 screenshots not yet
captured, so the report compiles end-to-end right now. Replace the PNG
files this writes (same filenames) with real screenshots later --
no LaTeX changes needed when you do.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

NAMES = [
    ("metrics-dashboard-charts.png", "Metrics dashboard (charts view)"),
    ("guided-tour.png", "Guided tour, mid-sequence"),
    ("langsmith-trace.png", "LangSmith trace group"),
]

out_dir = Path(__file__).resolve().parent.parent / "assets" / "screenshots"
out_dir.mkdir(parents=True, exist_ok=True)

for filename, label in NAMES:
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    ax.set_facecolor("#f3f4f6")
    fig.patch.set_facecolor("#f3f4f6")
    ax.text(
        0.5,
        0.55,
        "PLACEHOLDER",
        ha="center",
        va="center",
        fontsize=28,
        color="#9ca3af",
        fontweight="bold",
    )
    ax.text(
        0.5,
        0.4,
        f"Replace with: {label}",
        ha="center",
        va="center",
        fontsize=13,
        color="#6b7280",
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_edgecolor("#d1d5db")
    fig.tight_layout()
    fig.savefig(out_dir / filename)
    plt.close(fig)
    print(f"wrote {out_dir / filename}")
