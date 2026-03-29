# Valgtest – Politisk Kompas

A data-driven political compass for the Danish 2026 general election (*Folketingsvalget 2026*), built by scraping DR's Kandidattest and fitting a 2-dimensional Item Response Theory model to the answers.

![Politisk kompas](political_compass.png)

## What is this?

DR (Danish public broadcaster) runs a *Kandidattest* where every candidate for parliament answers 25 political questions on a 1–5 scale (strongly disagree → strongly agree). This project collects all those answers and uses a psychometric model to place every candidate — and their party — in a 2D political space, without any manual labelling of axes.

## Data

- **25 questions** covering topics like taxation, immigration, climate, welfare, and foreign policy
- **933 candidates** scraped across all 92 constituencies
- **883 candidates** with complete answers (the remaining 50 chose not to fill in the questionnaire)

The raw data is in `questions.json`, `candidates.json`, and `abilities.csv`.

## Methodology

### 1. Scraping (`scrape.py`)

DR's site is a Next.js app that embeds data as JSON inside `__next_f.push(...)` script tags in the HTML. The scraper:

1. Fetches all 92 valid constituency pages and extracts candidate `urlKey` identifiers from the escaped JSON payloads
2. Fetches each candidate's profile page and extracts their `candidateAnswers` array (QuestionID → 1–5 answer)
3. Fetches the 25 questions once from DR's public API: `GET /api/GetQuestions?districtId=4`

### 2. IRT Model (`analyze.py`)

Rather than doing PCA on raw responses, we fit a **multidimensional Graded Response Model (GRM)** — a psychometric model designed for ordinal data. The GRM:

- Models each answer as an ordinal response drawn from a latent trait distribution
- Estimates item parameters (discrimination and difficulty thresholds per question) and person parameters (ability coordinates per candidate) jointly via **Marginal Maximum Likelihood (MML)**
- Uses a 21×21 Gauss-Hermite quadrature grid for numerical integration over the 2D latent space

We fit **2 latent dimensions**, giving each candidate a coordinate `(θ₁, θ₂)` that captures the two dominant axes of political variation across the 25 questions.

Implementation uses the [`girth`](https://github.com/eribean/girth) library (`multidimensional_grm_mml`).

### 3. Varimax Rotation

The raw GRM solution is rotationally indeterminate (any orthogonal rotation of the factor space fits equally well). We apply **varimax rotation** to the discrimination matrix to make the axes more interpretable — this maximises the variance of the squared loadings, pushing each question to load heavily on one dimension and weakly on the other.

### 4. Axis Interpretation

The two rotated dimensions separate the parties as follows:

| | Dim 1 (x) | Dim 2 (y) |
|---|---|---|
| **High (+)** | Enhedslisten, Alternativet, SF | Moderaterne, Radikale, Liberal Alliance |
| **Low (−)** | Liberal Alliance, Venstre, DF | Dansk Folkeparti, Borgernes Parti, Danmarksdemokraterne |

**Dim 1** is a classic **economic left/right** axis. Questions loading heavily here include redistribution, welfare, and labour market issues.

**Dim 2** separates **social-liberal** parties (high) from **nationalist/populist** parties (low). Questions loading here include immigration policy, foreign aid, and attitudes toward democratic values.

Notably, **Dansk Folkeparti** is a strong outlier on Dim 2 (very low), sitting far from the rest of the right wing.

## Reproducing

```bash
pip install requests beautifulsoup4 girth numpy matplotlib scipy

# Scrape all candidates (~5 min, resumable)
python scrape.py

# Fit the IRT model and generate the plot (~1 min)
python analyze.py

# Re-plot from saved abilities.csv (instant)
python plot.py
```

> **Note:** `girth 0.8.0` uses the deprecated `scipy.stats.mvn.mvnun` API (removed in SciPy 2.0). The two patches in `scrape.py` comments fix this for newer SciPy versions — see the source for details.
