# NeighborHealth 2.0: design

Why the system is built the way it is. For how to run it, see the [README](README.md); for measured
numbers, see the [data card](docs/v2/DATA_CARD.md) and [model card](docs/v2/MODEL_CARD.md).

## 1. What problem, for whom

Bengaluru reports thousands of dengue cases a year, mostly noticed after they peak. The only public,
machine-readable-ish source is the Karnataka NVBDCP daily bulletin, a PDF per day.

| Person | What they need | What the system gives them |
|---|---|---|
| Resident | "Should I worry this week, near my home?" | Ward risk with a range, alerts for saved places in English, Kannada and Hindi, a way to report breeding spots, answers from official guidelines |
| Health official | "Where do I send a team first?" | A queue of photo-checked reports, field tasks with an audit trail, optimised inspection routes |

## 2. Principles (each one is enforced in code, not just stated)

| Principle | How it is enforced |
|---|---|
| **Real data only** | No synthetic data in v2. v1's synthetic files are not tracked or read. Every number traces to a bulletin, NASA POWER, or the 2011 Census. |
| **Say how sure you are** | Forecasts carry 50/80/95% ranges; ward values are labelled estimates; the map fades uncertain wards. |
| **Never score on invented numbers** | Weeks filled in by interpolation across missing bulletins are excluded from backtest scoring (`ml/backtest.py`, `scored_weeks`). |
| **Refuse rather than guess** | OCR accepts a reading only if it passes arithmetic checks; the assistant answers only from retrieved official passages and refuses out-of-scope questions; the alert engine will not run on a stale forecast. |
| **Safety before helpfulness** | Warning signs of severe dengue trigger "go to hospital / call 108" with the nearest hospitals before anything else. The assistant never diagnoses. |
| **Always let people stop** | Every alert carries an opt-out that actually works (signed email link; verified Twilio STOP webhook). Users can export and delete their data. |
| **Config, not code** | City-specific settings live in `config/cities/bengaluru.yaml`. |

## 3. Architecture

```
ICTS archive (606 PDFs, 2021-09 to 2024-11)          NASA POWER weather        Census 2011 + ward polygons
        │                                                    │                            │
        ▼                                                    ▼                            │
 pipeline/  download → parse (text) / OCR (scans) → validate → reconcile → weekly series  │
        │                                                                                 │
        ▼                                                                                 ▼
 ml/   6 models → rolling backtest (observed weeks only) → conformal intervals → SHAP → ward allocation
        │     → registry + quality gate → publish latest.json (+ drift report, model card)
        ▼
 apps/api (FastAPI)  forecast · wards · reports · officials · alerts · assistant · privacy · pilot
        │                    │                         │
   SQLite / Postgres   Redis Streams → worker → email / SMS / WhatsApp
        │
 apps/web (Next.js)  residents + health team
```

## 4. Key decisions and the reasons behind them

### 4.1 Parsing the bulletins by column position, not by counting numbers
Real bulletins leave cells blank all the time: the whole "on the day" block on most rows, the deaths cell on
some, the blocks cell on the BBMP row. A row with six numbers could be on-day or cumulative; counting cannot tell.
The parser measures the 17 numeric column positions from the always-complete **Total** row on each page and assigns every
number to its nearest column. It also drops rotated margin footnotes and collapses rows printed twice.
*Check that needs no hand labels:* the 30 district rows must sum to the printed state total. This holds for 374 of 379 text bulletins.

### 4.2 OCR for scanned bulletins, limited to the two rows that matter
From Oct 2023 most files are scans. Whole-page OCR garbled digits, so the extractor deskews, finds the
Total and BBMP rows, removes the ruled lines (they read as `1`, `l`, `|`), re-reads each row at several scales and votes.
A reading is accepted only if IgM + NS1 = Total and Total ≤ Samples ≤ Suspected. The cumulative block is located
by x-position learned from the page itself; if it cannot be located, **nothing is accepted**, because a lone block could be the
on-the-day numbers. Output is committed (`extracted_rule.jsonl`) because OCR needs macOS.

### 4.3 Weekly cases from cumulative counts
Bulletins are missing on many days, so summing "on the day" numbers would undercount. Weekly cases are differences of the
year-to-date cumulative at consecutive Sundays. The cumulative is grouped by the year it *refers to*, because early-January files can
be the previous year's final report. Points that break monotonicity within a year are dropped.

### 4.4 Honest evaluation
Rolling-origin backtest (train on weeks ≤ t, forecast t+h), baselines (persistence, seasonal naive), conformal intervals built
only from residuals observable at each origin, WIS and interval coverage. The promotion gate requires beating seasonal naive
on MAE averaged over horizons and 80% coverage in 0.65–0.95. **Result:** the ensemble beats the baseline at 1 week (about 14% lower MAE)
and not at 3–4 weeks; the averaged skill sits within ±0.01 of zero, so whether a model is "promoted" depends on how often models are refit.
That is a finding about the amount of data (161 weeks), not something to tune away.

### 4.5 Ward risk is an allocation, not a measurement
Cases are only reported for BBMP as a whole. Ward numbers split the city forecast by estimated population and risk factors,
with Monte Carlo uncertainty, and are always labelled estimates.

### 4.6 The assistant: retrieval first, language model second
Keyword (BM25) retrieval over WHO and NCVBDC documents, with light stemming, a small reviewable lay→technical synonym list,
page titles as searchable text, and boilerplate/bibliography filtered out. A **relevance gate** weights each question term by rarity
and refuses if the passages do not cover it; words the corpus has never seen (a city, a sport) count against the match.
With an LLM key, answers are written from the passages and citations are verified; without one, the best passages are shown verbatim.
Measured: recall@3 0.96 on the set it was tuned on, 0.5 on a fresh set; all 9 out-of-scope questions refused. The known ceiling of keyword search is the
reason embeddings + a reranker are the next step.

### 4.7 Alerts are opt-in, capped, and stale-proof
Saved places map to wards; alerts fire only on upward threshold crossings (hysteresis), de-duplicated per place and week, capped at two a week,
held during quiet hours. The engine refuses to run when the forecast data is older than 21 days, and `/health` measures the age of the
**data**, not of the file. Delivery is dry-run by default.

### 4.8 Privacy by construction
Photos have EXIF stripped; the public report list never shows names or photos; deletion removes the account, photos and logs but keeps
open field tasks (unlinked from the person) and attributes official audit entries to `deleted-user`.

## 5. Interface design

*What the code defines today (`apps/web`); the pages have not been built or reviewed yet, so treat this as the design intent that the UI pass must meet.*

| Element | Choice | Reason |
|---|---|---|
| Palette | Rain-paper off-white `244 247 246`, monsoon ink `#14213D`, lake teal `#0E7C7B` for actions; dark mode with the same roles | Calm and readable; theme tokens are CSS variables so light/dark stay in sync |
| Risk ramp | Sage `#DCE8D2` → marigold `#F2B33D` → `#E06A2C` → kumkum `#9E2338` | Sequential, distinguishable for colour-blind users; never the only cue (bands are also labelled) |
| Type | IBM Plex Sans + Plex Sans Devanagari + Noto Sans Kannada; Plex Sans Condensed for numbers; tabular figures | One voice across three scripts; numbers align |
| Scale | Modular 1.25: body 16 px, small 13–14 px, display up to 49 px | Consistent rhythm; 16 px body avoids mobile zoom |
| Signature | Home leads with the live forecast **fan chart** (50/80/95% bands) with rainfall bars below on the same timeline | Shows rain leading cases and the uncertainty together |
| Map | Full-bleed ward map; fill colour = estimated band, **fill opacity = certainty**; week selector; side panel / mobile bottom sheet | Uncertainty is visible, not buried |
| Ward panel | Rate per 100k with 80% range bar, chance of high risk, next 4 weeks, drivers, "explain in plain words", alert-me | Everything needed to decide, in one place |
| Pages | Home · Risk map · Forecast (with backtest table) · Report a spot · Alerts · Ask · Health team · How it works · Sign in | Methodology is a first-class page |
| Navigation | Top bar on desktop, bottom tab bar on phones with safe-area padding, skip-to-content link | Thumb reach; keyboard and screen-reader access |
| Accessibility floor | Visible focus ring, `prefers-reduced-motion` respected, light/dark, three languages | |
| Freshness | The UI must show the date of the data behind every forecast and a clear "out of date" state | The archive ends 2024-11-04; a stale forecast must never look live |

## 6. Known gaps

- **Data ends 2024-11-04.** Nothing live can be promised until a fresh source exists (the Ministry's annual state table is a validation source, not a weekly one).
- No automated UI tests; Kannada/Hindi text needs native review (`docs/v2/TRANSLATION_REVIEW.md`), and new interface strings are English until reviewed.
- Photo check is off by default (`VISION_ENABLED=false`); no automatic face/number-plate blurring.
- Retrieval is keyword-only; non-English questions need an LLM key to be translated for search.
- Rate limiting is per-process; token is stored in `localStorage` rather than an httpOnly cookie.
- PostGIS columns exist, but most spatial queries use the Python fallback.
- Not yet done: deployment to a host, a data-retention rule, a live-data source.
