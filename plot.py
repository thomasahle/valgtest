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
    "Radikale Venstre":                           "#5C2D8F",
    "Det Konservative Folkeparti":                "#6BAA3A",
    "SF - Socialistisk Folkeparti":               "#E07BA0",
    "Borgernes Parti - Lars Boje Mathiesen":      "#45B5A8",
    "Liberal Alliance":                           "#3AAFC4",
    "Moderaterne":                                "#9B7FC8",
    "Dansk Folkeparti":                           "#D4B800",
    "Venstre, Danmarks Liberale Parti":           "#1A3567",
    "Danmarksdemokraterne \u2012 Inger Støjberg": "#8090B8",
    "Enhedslisten \u2013 De Rød-Grønne":          "#E07820",
    "Alternativet":                               "#3A7E32",
    "Uden for parti":                             "#888888",
}

SHORT_NAMES = {
    "Socialdemokratiet":                          "Socialdemokratiet",
    "Radikale Venstre":                           "Radikale Venstre",
    "Det Konservative Folkeparti":                "Konservative",
    "SF - Socialistisk Folkeparti":               "SF",
    "Borgernes Parti - Lars Boje Mathiesen":      "Borgernes Parti",
    "Liberal Alliance":                           "Liberal Alliance",
    "Moderaterne":                                "Moderaterne",
    "Dansk Folkeparti":                           "Dansk Folkeparti",
    "Venstre, Danmarks Liberale Parti":           "Venstre",
    "Danmarksdemokraterne \u2012 Inger Støjberg": "Danmarksdemokraterne",
    "Enhedslisten \u2013 De Rød-Grønne":          "Enhedslisten",
    "Alternativet":                               "Alternativet",
    "Uden for parti":                             "Uden for parti",
}


def confidence_ellipse(ax, x, y, color, n_std=1.0, alpha=0.15):
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
        edgecolor=color, linewidth=1.5,
    )
    ax.add_patch(ell)


rows = list(csv.DictReader(open("abilities.csv")))
names   = [r["name"]  for r in rows]
parties = [r["party"] for r in rows]
xs = np.array([float(r["dim1"]) for r in rows])
ys = np.array([float(r["dim2"]) for r in rows])

fig, ax = plt.subplots(figsize=(12, 12))

unique_parties = sorted(set(parties))

# Individual candidates
for i in range(len(rows)):
    color = PARTY_COLORS.get(parties[i], "#888888")
    ax.scatter(xs[i], ys[i], c=color, s=18, alpha=0.35, linewidths=0, zorder=2)

# Party ellipses + mean dots + labels
for party in unique_parties:
    mask = np.array([p == party for p in parties])
    if mask.sum() < 2:
        continue
    px, py = xs[mask], ys[mask]
    color = PARTY_COLORS.get(party, "#888888")
    confidence_ellipse(ax, px, py, color=color, n_std=1.0)
    mx, my = px.mean(), py.mean()
    ax.scatter(mx, my, c=color, s=200, zorder=5, edgecolors="black", linewidths=0.8)
    label = SHORT_NAMES.get(party, party)
    ax.annotate(
        label, (mx, my),
        fontsize=9, fontweight="bold", color=color,
        ha="center", va="bottom",
        xytext=(0, 11), textcoords="offset points",
        bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="none"),
    )

ax.axhline(0, color="black", linewidth=0.5, zorder=0)
ax.axvline(0, color="black", linewidth=0.5, zorder=0)
ax.set_xlabel("Latent Dimension 1", fontsize=13)
ax.set_ylabel("Latent Dimension 2", fontsize=13)
ax.set_title("Politisk kompas – DR Kandidattest (2D IRT/GRM)", fontsize=15)
ax.set_aspect("equal")
plt.tight_layout()
plt.savefig("political_compass.png", dpi=150)
print("Saved political_compass.png")
