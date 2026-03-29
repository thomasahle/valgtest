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

#### Dim 1 — Omfordeling / Klassisk venstre–højre

Top 10 questions by absolute loading on Dim 1:

| Loading | Topic | Question |
|---:|---|---|
| −3.86 | Økonomi | Staten skal skære i støtten til Danmarks Radio |
| +3.80 | Skat | Boligejere der tjener på prisstigninger skal betale mere i skat |
| +3.65 | Transport | Vigtigere at investere i tog og busser end i motorveje |
| −3.56 | Udlændinge | Vigtigere at udvise kriminelle udlændinge end at overholde internationale konventioner |
| −3.56 | Udlændinge | Danmark skal bruge færre penge på udviklingsbistand |
| +3.52 | Social | Større udligning mellem rige og fattige kommuner (overførselsindkomst) |
| −3.48 | Udlændinge | Ansøgere om statsborgerskab skal screenes for antidemokratiske holdninger |
| −3.16 | Social | OK at ulighed stiger, så længe alle bliver rigere |
| +3.11 | Skat | Skatten for de højeste indkomster skal sættes op |
| −2.94 | Skole | Lettere at smide elever ud, hvis deres adfærd skaber problemer |

The top 10 splits roughly evenly between economic questions (property tax, public transport, municipal equalisation, income tax) and immigration/cultural questions (deporting criminals, foreign aid, citizenship screening, school discipline). These two clusters load at nearly identical magnitude — 3 of the top 7 items are immigration-related. They cannot be separated by any orthogonal rotation, meaning that among Danish candidates, immigration attitudes and economic attitudes are so tightly correlated that they form a single dimension.

#### Dim 2 — Reformisme / Populisme

Top 10 questions by absolute loading on Dim 2:

| Loading | Topic | Question |
|---:|---|---|
| +2.34 | Økonomi | Folkepensionsalderen skal fortsat stige med levealderen |
| −1.51 | Økonomi | Store Bededag skal genindføres som helligdag |
| +1.68 | Økonomi | Åbn for mere udenlandsk arbejdskraft fra lande uden for Europa |
| +1.50 | Regeringsdannelse | Det vil være bedst med en regering hen over midten |
| −1.28 | Økonomi | Danmark bruger for mange penge på at støtte Ukraine |
| −1.22 | Transport | Afgifter på benzin og diesel skal sænkes |
| −1.14 | Skat | Skatten for de højeste indkomster skal sættes op |
| −1.09 | Økonomi | Politikerne skal arbejde for at sætte arbejdstiden ned |
| +1.09 | Social | OK at ulighed stiger, så længe alle bliver rigere |
| +1.07 | Social | Vigtigere at skaffe ansatte til ældrepleje end at de taler dansk |

After controlling for Dim 1, the second axis is defined by pension reform, the Store Bededag holiday, Ukraine aid, cross-party government, and foreign labour. These cluster around a reformist/technocratic vs populist/protest dimension. High Dim 2 = support for pension reform, Ukraine aid, cross-party governance, and foreign labour (Moderaterne, Radikale, Liberal Alliance). Low Dim 2 = opposition to these (Dansk Folkeparti, Danmarksdemokraterne, Borgernes Parti).

Notably, Dansk Folkeparti is a strong outlier on Dim 2 (very low), sitting far from the rest of the right wing — captured here by their opposition to pension reform and Ukraine support rather than immigration stance (which loads on Dim 1, shared with most of the right).

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
