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

The raw GRM solution is rotationally indeterminate (any orthogonal rotation of the factor space fits the data equally well). We apply **varimax rotation** to the discrimination matrix to make the axes as interpretable as possible.

Varimax maximises the variance of squared loadings — it pushes each question toward loading heavily on *one* dimension and near-zero on the other (simple structure). This is the standard psychometric criterion for choosing a rotation without external constraints.

**Why not anchor on party positions (e.g. Enhedslisten ↔ Liberal Alliance as the x-axis)?**

We tested this and quantified the difference:

| Metric | Varimax | Party-anchored |
|---|---|---|
| Simple structure score | **28.1** | 23.0 |
| Mean item complexity (Hofmann) | **1.293** | 1.425 |

Varimax wins on both standard criteria. The party-anchored rotation sacrifices item-level simple structure to make party *positions* more intuitive — a tradeoff, not an improvement. Varimax is the principled choice.

### 4. Axis Orientation

After varimax, we fix the two sign ambiguities using well-known anchor parties (any orthogonal rotation that only flips signs is equally valid):

- **Dim 1 (x)**: flipped so Liberal Alliance is right, Enhedslisten is left
- **Dim 2 (y)**: flipped so Dansk Folkeparti is top, Radikale Venstre is bottom

### 5. Question Loadings

The table below shows the varimax-rotated discrimination loadings for all 25 questions (sorted by |loading| on Dim 1). A high absolute loading means that question strongly discriminates along that dimension.

| Topic | Question (short) | Dim 1 | Dim 2 |
|---|---|---:|---:|
| Økonomi | Skær i støtten til Danmarks Radio | **−3.86** | −0.37 |
| Skat | Boligskat på stigninger | **+3.80** | −0.45 |
| Transport | Investér i tog/bus frem for motorveje | **+3.65** | −0.11 |
| Udlændinge | Udvise kriminelle uden hensyn til konventioner | **−3.56** | −0.70 |
| Udlændinge | Færre penge til udviklingsbistand | **−3.56** | −0.68 |
| Social | Større udligning rige/fattige kommuner | +3.52 | −0.73 |
| Udlændinge | Screen statsborgerskabsansøgere for antidemokratiske holdninger | **−3.48** | −0.75 |
| Klima | Atomkraft på dansk jord | −2.84 | +0.21 |
| Transport | Sænk afgifter på benzin/diesel | −2.88 | −1.22 |
| Skole | Lettere at smide elever ud | −2.94 | −0.14 |
| Social | OK at ulighed stiger, så alle bliver rigere | **−3.16** | +1.09 |
| Skat | Højeste indkomster: sæt skatten op | +3.11 | −1.14 |
| Klima | Forbyd sprøjtning på sårbare drikkevandsområder | +2.56 | −0.02 |
| Økonomi | Sæt arbejdstiden ned | +2.67 | −1.09 |
| Klima | Hensyn til lokalbefolkning ved solceller | −2.21 | −0.65 |
| Økonomi | Mere udenlandsk arbejdskraft udefra Europa | +1.50 | **+1.68** |
| Økonomi | Folkepensionsalderen skal fortsat stige | −1.57 | **+2.34** |
| Regeringsdannelse | Regering hen over midten | +0.54 | **+1.50** |
| Social | Ansatte i ældrepleje behøver ikke tale dansk | +1.07 | +1.07 |
| Sundhed | Sæt prisen på cigaretter markant op | +1.21 | +0.50 |
| Social | Større udligning rige/fattige kommuner | +1.03 | −0.58 |
| Skole | Flere børn i specialklasse | −0.73 | −0.66 |
| Skat | Sænk momsen på fødevarer | +0.29 | −0.84 |
| Økonomi | Danmark bruger for mange penge på Ukraine | −0.54 | **−1.28** |
| Økonomi | Store Bededag skal genindføres | −0.43 | **−1.51** |

#### Interpreting the axes

**Dim 1 — Omfordeling / Klassisk venstre–højre**

The questions with the largest absolute loadings on Dim 1 are all about redistribution, public spending, and the role of the state in the economy: property tax on housing gains, investment in public transport vs roads, cutting support for DR, welfare transfers, and income tax on the highest earners. This is a textbook economic left–right axis.

Immigration questions (udvise kriminelle, bistand, statsborgerskab) also load strongly on Dim 1 — they are not separable from the economic axis in these data by any orthogonal rotation. This means Danish immigration attitudes and economic attitudes are so correlated among candidates that they lie on the same dimension.

**Dim 2 — Reformisme / Populisme**

After controlling for Dim 1, the second axis is defined by questions about the retirement age, the Store Bededag holiday, Ukraine aid, cross-party government, and foreign labour. These are not obviously "immigration vs not" — they cluster around a reformist/technocratic vs populist/protest dimension. High Dim 2 = support for pension reform, Ukraine aid, cross-party governance, and foreign labour (Moderaterne, Radikale, Liberal Alliance). Low Dim 2 = opposition to these (Dansk Folkeparti, Danmarksdemokraterne, Borgernes Parti).

Notably, Dansk Folkeparti is a strong outlier on Dim 2 (very low), sitting far from the rest of the right wing — captured here by their strong opposition to pension reform and Ukraine support rather than their immigration stance (which loads on Dim 1, shared with most of the right).

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

> **Note:** `girth 0.8.0` uses the deprecated `scipy.stats.mvn.mvnun` API (removed in SciPy 2.0). Two patches are required for newer SciPy — see comments in the source for details.
