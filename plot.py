#!/usr/bin/env python3
"""Re-plot the political compass from abilities.csv (no refitting needed)."""

import csv
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

# (label, x_offset, y_offset, ha)
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


rows = list(csv.DictReader(open("abilities.csv")))
names   = [r["name"]  for r in rows]
parties = [r["party"] for r in rows]
xs = np.array([float(r["dim1"]) for r in rows])
ys = np.array([float(r["dim2"]) for r in rows])

# ── Theoretically grounded rotation ──────────────────────────────────────────
# Axis 1 (x) anchored on pure redistribution/tax/welfare questions:
#   Q1270 boligskat op (+), Q1285 topskat op (+), Q1305 overførselsindkomst op (+),
#   Q1288 ulighed okay (−), Q1289 udligning kommuner (+), Q1306 kortere arbejdstid (+)
# The least-squares direction of this composite in the 2D IRT space is [+0.932, −0.363].
#
# Axis 2 (y) is the orthogonal complement. After controlling for economy, it is
# driven by: pension reform, foreign labour, Ukraine support, Store Bededag,
# development aid — a Nationalist/Protectionist ↔ Internationalist/Reform axis.
# Negated so that nationalist parties (DF, DD, BP) score high (top of plot).
#
# Both directions are pre-computed from the IRT output — see the analysis in
# the repo README for the full derivation.

ECON_DIR = np.array([+0.932, -0.363])   # left (Enhedslisten) → right (LA)
NAT_DIR  = np.array([-0.363, -0.932])   # high = nationalist/protectionist (DF)

R = np.array([ECON_DIR, NAT_DIR])
coords = R @ np.array([xs, ys])
xs, ys = coords[0], coords[1]

# ── Figure setup ──────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(11, 11), facecolor="white")
ax.set_facecolor("white")

# Remove all spines
for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

# Light grid
ax.grid(True, color="#dddddd", linewidth=0.8, zorder=0)
ax.set_axisbelow(True)

# Center lines
ax.axhline(0, color="#aaaaaa", linewidth=1.0, zorder=1)
ax.axvline(0, color="#aaaaaa", linewidth=1.0, zorder=1)

# ── Data ──────────────────────────────────────────────────────────────────────
unique_parties = sorted(set(parties))

# Individual candidates (small dots)
for i in range(len(rows)):
    color = PARTY_COLORS.get(parties[i], "#999999")
    ax.scatter(xs[i], ys[i], c=color, s=14, alpha=0.35, linewidths=0, zorder=2)

# Ellipses
for party in unique_parties:
    mask = np.array([p == party for p in parties])
    if mask.sum() < 3:
        continue
    color = PARTY_COLORS.get(party, "#999999")
    confidence_ellipse(ax, xs[mask], ys[mask], color=color, n_std=1.0)

# Party mean dots + labels
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
            ha=ha, va=va, linespacing=1.2, zorder=6)

# ── Axis labels ───────────────────────────────────────────────────────────────
xlim = ax.get_xlim()
ylim = ax.get_ylim()

# Expand limits slightly for labels
pad = 0.3
ax.set_xlim(xlim[0] - pad, xlim[1] + pad)
ax.set_ylim(ylim[0] - pad, ylim[1] + pad)
xlim = ax.get_xlim()
ylim = ax.get_ylim()

kw = dict(transform=ax.transData, clip_on=False, va="center")

# x-axis: bottom, with direction hints
ax.text(np.mean(xlim), ylim[0] - 0.15, "Økonomi",
        ha="center", va="top", fontsize=12, color="#555555", transform=ax.transData, clip_on=False)
ax.text(xlim[0] + 0.05, ylim[0] - 0.15, "← Venstre",
        ha="left", va="top", fontsize=10, color="#888888", transform=ax.transData, clip_on=False)
ax.text(xlim[1] - 0.05, ylim[0] - 0.15, "Højre →",
        ha="right", va="top", fontsize=10, color="#888888", transform=ax.transData, clip_on=False)

# y-axis: left side, with direction hints
ax.text(xlim[0] - 0.15, np.mean(ylim), "Nationalisme / Globalisme",
        ha="right", va="center", fontsize=12, color="#555555",
        rotation=90, transform=ax.transData, clip_on=False)
ax.text(xlim[0] - 0.15, ylim[1] - 0.05, "Nationalistisk ↑",
        ha="right", va="top", fontsize=10, color="#888888",
        rotation=90, transform=ax.transData, clip_on=False)
ax.text(xlim[0] - 0.15, ylim[0] + 0.05, "↓ Internationalistisk",
        ha="right", va="bottom", fontsize=10, color="#888888",
        rotation=90, transform=ax.transData, clip_on=False)

# ── Title ─────────────────────────────────────────────────────────────────────
fig.text(0.05, 0.97, "Folketingets partier på to akser",
         ha="left", va="top", fontsize=22, fontweight="bold", color="#111111")
fig.text(0.05, 0.935, "Data: DR's kandidattest, FV26  •  2D IRT/GRM model  •  Små prikker = individuelle kandidater",
         ha="left", va="top", fontsize=9, color="#777777")

ax.set_aspect("equal")
plt.tight_layout(rect=[0, 0, 1, 0.93])
plt.savefig("political_compass.png", dpi=150, bbox_inches="tight", facecolor="white")
print("Saved political_compass.png")
