#!/usr/bin/env python3
"""
Fit a 2D multidimensional GRM to the kandidattest data and plot a political compass.

Requires:
  questions.json, candidates.json  (from scrape.py)
  pip install girth numpy matplotlib scipy
"""

import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from scipy.stats import zscore

# girth must be installed: pip install girth
from girth import multidimensional_grm_mml


# ── Party colours (official) ─────────────────────────────────────────────────
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

MIN_ANSWERS = 20  # drop candidates with fewer answered questions


def load_data():
    questions = json.loads(Path("questions.json").read_text())
    candidates = json.loads(Path("candidates.json").read_text())

    # Map QuestionID → index (API uses "Id", candidate answers use "QuestionID")
    qids = [q.get("Id") or q.get("QuestionID") or q.get("id") for q in questions]
    qid_to_idx = {qid: i for i, qid in enumerate(qids)}
    n_q = len(qids)

    # Build response matrix (n_questions × n_candidates), NaN for missing
    names, parties = [], []
    cols = []
    for c in candidates:
        answers = {a["QuestionID"]: a["Answer"] for a in c.get("answers", [])}
        if len(answers) < MIN_ANSWERS:
            continue
        col = np.array([answers.get(qid, np.nan) for qid in qids], dtype=float)
        cols.append(col)
        names.append(c.get("name") or c.get("urlKey"))
        parties.append(c.get("party") or "Ukendt")

    data = np.column_stack(cols)  # (n_questions, n_candidates)
    print(f"Data matrix: {data.shape[0]} questions × {data.shape[1]} candidates")

    # Drop questions with >30% missing
    miss = np.isnan(data).mean(axis=1)
    keep_q = miss < 0.3
    data = data[keep_q]
    kept_qids = [qids[i] for i, k in enumerate(keep_q) if k]
    kept_questions = [questions[i] for i, k in enumerate(keep_q) if k]
    print(f"After dropping sparse questions: {data.shape[0]} questions remain")

    # Impute remaining NaN with row median (per question)
    for i in range(data.shape[0]):
        row = data[i]
        median = np.nanmedian(row)
        row[np.isnan(row)] = median
    data = np.round(data).astype(int)
    data = np.clip(data, 1, 5)

    return data, names, parties, kept_questions


def confidence_ellipse(ax, x, y, color, n_std=1.0, alpha=0.15, **kwargs):
    if len(x) < 3:
        return
    cov = np.cov(x, y)
    eigvals, eigvecs = np.linalg.eigh(cov)
    # Sort descending
    order = eigvals.argsort()[::-1]
    eigvals, eigvecs = eigvals[order], eigvecs[:, order]
    angle = np.degrees(np.arctan2(*eigvecs[:, 0][::-1]))
    width, height = 2 * n_std * np.sqrt(np.abs(eigvals))
    ell = Ellipse(
        xy=(np.mean(x), np.mean(y)),
        width=width, height=height,
        angle=angle,
        facecolor=color, alpha=alpha,
        edgecolor=color, linewidth=1.2,
        **kwargs,
    )
    ax.add_patch(ell)


def varimax(loadings, max_iter=1000, tol=1e-6):
    """Simple varimax rotation."""
    p, k = loadings.shape
    rotation = np.eye(k)
    for _ in range(max_iter):
        old = rotation.copy()
        for i in range(k):
            for j in range(i + 1, k):
                x = loadings @ rotation
                u = x[:, i] ** 2 - x[:, j] ** 2
                v = 2 * x[:, i] * x[:, j]
                A = np.sum(u)
                B = np.sum(v)
                C = np.sum(u ** 2 - v ** 2)
                D = np.sum(u * v)
                num = D - A * B / p
                den = C - (A ** 2 - B ** 2) / p
                theta = np.arctan2(2 * num, den) / 4
                c, s = np.cos(theta), np.sin(theta)
                rot = np.eye(k)
                rot[i, i] = c; rot[j, j] = c
                rot[i, j] = -s; rot[j, i] = s
                rotation = rotation @ rot
        if np.max(np.abs(rotation - old)) < tol:
            break
    return loadings @ rotation, rotation


def main():
    print("Loading data...")
    data, names, parties, questions = load_data()

    print("Fitting 2D multidimensional GRM (this may take a minute)...")
    results = multidimensional_grm_mml(data, 2, {
        "quadrature_n": 21,
        "use_LUT": True,
        "max_iteration": 500,
    })

    abilities = results["Ability"]          # (2, n_candidates)
    discrimination = results["Discrimination"]  # (n_items, 2)

    # Varimax rotation for interpretability
    rotated_disc, R = varimax(discrimination)
    abilities_rot = R.T @ abilities         # (2, n_candidates)

    # Save abilities to CSV
    import csv
    with open("abilities.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "party", "dim1", "dim2"])
        for i, (name, party) in enumerate(zip(names, parties)):
            w.writerow([name, party, abilities_rot[0, i], abilities_rot[1, i]])
    print("Saved abilities.csv")

    # Print top questions loading on each dimension
    print("\nTop 5 questions loading on Dim 1 (after varimax):")
    order1 = np.argsort(np.abs(rotated_disc[:, 0]))[::-1]
    for idx in order1[:5]:
        q = questions[idx]
        title = q.get("Title") or q.get("title") or str(q.get("Id") or q.get("QuestionID"))
        print(f"  {rotated_disc[idx, 0]:.3f}  {title}")

    print("\nTop 5 questions loading on Dim 2 (after varimax):")
    order2 = np.argsort(np.abs(rotated_disc[:, 1]))[::-1]
    for idx in order2[:5]:
        q = questions[idx]
        title = q.get("Title") or q.get("title") or str(q.get("Id") or q.get("QuestionID"))
        print(f"  {rotated_disc[idx, 1]:.3f}  {title}")

    # ── Plot ─────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 12))

    xs = abilities_rot[0]
    ys = abilities_rot[1]

    unique_parties = sorted(set(parties))

    # Individual candidates
    for i, (x, y) in enumerate(zip(xs, ys)):
        color = PARTY_COLORS.get(parties[i], "#888888")
        ax.scatter(x, y, c=color, s=18, alpha=0.4, linewidths=0, zorder=2)

    # Party means + ellipses + labels
    for party in unique_parties:
        mask = np.array([p == party for p in parties])
        if mask.sum() < 2:
            continue
        px, py = xs[mask], ys[mask]
        color = PARTY_COLORS.get(party, "#888888")
        confidence_ellipse(ax, px, py, color=color, n_std=1.0)
        mx, my = px.mean(), py.mean()
        ax.scatter(mx, my, c=color, s=180, zorder=5, edgecolors="black", linewidths=0.8)
        ax.annotate(
            party, (mx, my),
            fontsize=8, fontweight="bold", color=color,
            ha="center", va="bottom",
            xytext=(0, 10), textcoords="offset points",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.6, ec="none"),
        )

    ax.axhline(0, color="black", linewidth=0.5, zorder=0)
    ax.axvline(0, color="black", linewidth=0.5, zorder=0)
    ax.set_xlabel("Latent Dimension 1", fontsize=13)
    ax.set_ylabel("Latent Dimension 2", fontsize=13)
    ax.set_title("Politisk kompas – DR Kandidattest (2D IRT/GRM)", fontsize=15)
    ax.set_aspect("equal")
    plt.tight_layout()
    plt.savefig("political_compass.png", dpi=150)
    print("\nSaved political_compass.png")


if __name__ == "__main__":
    main()
