#!/usr/bin/env python3
"""
Re-plot the political compass from abilities.csv (no refitting needed).

Usage:
  python plot.py [data_dir]

  data_dir  directory containing abilities.csv (output of analyze.py)
            (default: current directory, i.e. DR data)

Axes are anchored on well-known Danish parties:
  X (Økonomi):     Enhedslisten (left) ← → Liberal Alliance (right)
  Y (Nationalisme): Radikale Venstre (internationalist) ↑ … ↓ Dansk Folkeparti (nationalist)
"""

import csv
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse

PARTY_COLORS = {
    "Socialdemokratiet":                          "#C8241A",
    "Radikale Venstre":                           "#E0197D",
    "Det Konservative Folkeparti":                "#6BAA3A",
    "SF - Socialistisk Folkeparti":               "#E8334A",
    "Borgernes Parti - Lars Boje Mathiesen":      "#1A7A78",
    "Liberal Alliance":                           "#3AAFC4",
    "Moderaterne":                                "#7B4FA0",
    "Dansk Folkeparti":                           "#D4A800",
    "Venstre, Danmarks Liberale Parti":           "#1A3567",
    "Danmarksdemokraterne \u2012 Inger Støjberg": "#4A78B0",
    "Enhedslisten \u2013 De Rød-Grønne":          "#E8412C",
    "Alternativet":                               "#2E8B3A",
    "Uden for parti":                             "#999999",
}

# (display_label, x_offset, y_offset, ha)  –  None skips the label
LABEL_OPTS = {
    "Socialdemokratiet":                          ("Social-\ndemokratiet",   0.0,  0.13, "center"),
    "Radikale Venstre":                           ("Radikale\nVenstre",      0.0,  0.13, "center"),
    "Det Konservative Folkeparti":                ("Konservative",           0.13, 0.0,  "left"),
    "SF - Socialistisk Folkeparti":               ("SF",                    -0.13, 0.0,  "right"),
    "Borgernes Parti - Lars Boje Mathiesen":      ("Borgernes\nParti",       0.13, 0.0,  "left"),
    "Liberal Alliance":                           ("Liberal\nAlliance",      0.13, 0.0,  "left"),
    "Moderaterne":                                ("Moderaterne",            0.13, 0.0,  "left"),
    "Dansk Folkeparti":                           ("Dansk\nFolkeparti",     -0.13, 0.0,  "right"),
    "Venstre, Danmarks Liberale Parti":           ("Venstre",                0.13, 0.0,  "left"),
    "Danmarksdemokraterne \u2012 Inger Støjberg": ("Danmarks-\ndemokraterne", 0.13, 0.0, "left"),
    "Enhedslisten \u2013 De Rød-Grønne":          ("Enhedslisten",          -0.13, 0.0,  "right"),
    "Alternativet":                               ("Alternativet",          -0.13, 0.0,  "right"),
    "Uden for parti":                             None,
}


def confidence_ellipse(ax, x, y, color, n_std=1.0, alpha=0.18):
    if len(x) < 3:
        return
    cov = np.cov(x, y)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = eigvals.argsort()[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]
    angle = np.degrees(np.arctan2(*eigvecs[:, 0][::-1]))
    width, height = 2 * n_std * np.sqrt(np.abs(eigvals))
    ell = Ellipse(
        xy=(np.mean(x), np.mean(y)),
        width=width, height=height, angle=angle,
        facecolor=color, alpha=alpha,
        edgecolor="none",
    )
    ax.add_patch(ell)


def party_mean(parties, xs, ys, name):
    mask = np.array([p == name for p in parties])
    if mask.sum() == 0:
        return None
    return np.array([xs[mask].mean(), ys[mask].mean()])


def compute_rotation(parties, xs, ys):
    """
    Use the varimax axes directly — no additional rotation.
    Just fix sign conventions so the plot reads intuitively:
      - flip dim1 so right-wing parties (LA, Venstre) are on the right
      - flip dim2 so DF is at the top and Radikale is at the bottom
    """
    # Check sign of dim1: Enhedslisten should be negative (left), LA positive (right)
    enh = party_mean(parties, xs, ys, "Enhedslisten \u2013 De Rød-Grønne")
    la  = party_mean(parties, xs, ys, "Liberal Alliance")
    s1 = -1.0 if (enh is not None and la is not None and enh[0] > la[0]) else 1.0

    # Check sign of dim2: DF should be positive (top), Radikale negative (bottom)
    df  = party_mean(parties, xs, ys, "Dansk Folkeparti")
    rad = party_mean(parties, xs, ys, "Radikale Venstre")
    s2 = -1.0 if (df is not None and rad is not None and df[1] < rad[1]) else 1.0

    return np.diag([s1, s2])


def main():
    data_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    source_name = data_dir.name if data_dir != Path(".") else "DR"

    rows = list(csv.DictReader(open(data_dir / "abilities.csv")))
    names   = [r["name"]  for r in rows]
    parties = [r["party"] for r in rows]
    xs = np.array([float(r["dim1"]) for r in rows])
    ys = np.array([float(r["dim2"]) for r in rows])

    # ── Axis rotation anchored on known parties ───────────────────────────────
    R = compute_rotation(parties, xs, ys)
    coords = R @ np.array([xs, ys])
    xs, ys = coords[0], coords[1]

    # ── Figure setup ──────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(11, 11), facecolor="white")
    ax.set_facecolor("white")

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

    ax.grid(True, color="#dddddd", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.axhline(0, color="#aaaaaa", linewidth=1.0, zorder=1)
    ax.axvline(0, color="#aaaaaa", linewidth=1.0, zorder=1)

    # ── Data ──────────────────────────────────────────────────────────────────
    unique_parties = sorted(set(parties))

    for i in range(len(rows)):
        color = PARTY_COLORS.get(parties[i], "#999999")
        ax.scatter(xs[i], ys[i], c=color, s=14, alpha=0.35, linewidths=0, zorder=2)

    for party in unique_parties:
        mask = np.array([p == party for p in parties])
        if mask.sum() < 3:
            continue
        color = PARTY_COLORS.get(party, "#999999")
        confidence_ellipse(ax, xs[mask], ys[mask], color=color, n_std=1.0)

    for party in unique_parties:
        opts = LABEL_OPTS.get(party)
        if opts is None:
            continue
        label, dx, dy, ha = opts
        mask = np.array([p == party for p in parties])
        if mask.sum() < 2:
            continue
        color = PARTY_COLORS.get(party, "#999999")
        mx, my = xs[mask].mean(), ys[mask].mean()
        ax.scatter(mx, my, c=color, s=220, zorder=5, linewidths=0)
        va = "bottom" if dy > 0 else ("top" if dy < 0 else "center")
        ax.text(mx + dx, my + dy, label,
                fontsize=11, fontweight="bold", color=color,
                ha=ha, va=va, linespacing=1.2, zorder=6,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                          edgecolor="none", alpha=0.75))

    # ── Axis labels ───────────────────────────────────────────────────────────
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    pad = 0.3
    ax.set_xlim(xlim[0] - pad, xlim[1] + pad)
    ax.set_ylim(ylim[0] - pad, ylim[1] + pad)
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()

    ax.text(np.mean(xlim), ylim[0] - 0.15, "Solidarisk-progressiv ↔ Borgerlig-stram",
            ha="center", va="top", fontsize=12, color="#555555",
            transform=ax.transData, clip_on=False)
    ax.text(xlim[0] + 0.05, ylim[0] - 0.15, "← solidarisk-progressiv",
            ha="left", va="top", fontsize=10, color="#888888",
            transform=ax.transData, clip_on=False)
    ax.text(xlim[1] - 0.05, ylim[0] - 0.15, "borgerlig-stram →",
            ha="right", va="top", fontsize=10, color="#888888",
            transform=ax.transData, clip_on=False)

    ax.text(xlim[0] - 0.15, np.mean(ylim), "Midterreformistisk ↔ Hverdagspopulistisk",
            ha="right", va="center", fontsize=12, color="#555555",
            rotation=90, transform=ax.transData, clip_on=False)
    ax.text(xlim[0] - 0.15, ylim[1] - 0.05, "hverdagspopulistisk ↑",
            ha="right", va="top", fontsize=10, color="#888888",
            rotation=90, transform=ax.transData, clip_on=False)
    ax.text(xlim[0] - 0.15, ylim[0] + 0.05, "↓ midterreformistisk",
            ha="right", va="bottom", fontsize=10, color="#888888",
            rotation=90, transform=ax.transData, clip_on=False)

    # ── Title ─────────────────────────────────────────────────────────────────
    # Nice display name for the data source
    source_label = {
        "dr": "DR's", "altinget": "Altingets", "tv2": "TV 2's", "jp": "JP's",
        "combined": "kombineret (DR + Altinget + TV 2)",
    }.get(source_name.lower(), source_name + "'s")
    fig.text(0.05, 0.97, "Folketingets partier på to akser",
             ha="left", va="top", fontsize=22, fontweight="bold", color="#111111")
    fig.text(0.05, 0.935,
             f"Data: {source_label} kandidattest, FV26  •  2D IRT/GRM model  •  Små prikker = individuelle kandidater",
             ha="left", va="top", fontsize=9, color="#777777")

    ax.set_aspect("equal")
    plt.tight_layout(rect=[0, 0, 1, 0.93])
    out_path = data_dir / "political_compass.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
