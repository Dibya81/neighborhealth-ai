# Step 1: Real data pipeline

**Goal:** replace v1's synthetic dataset with real dengue surveillance data, extracted from
government PDFs with a pipeline whose accuracy is *measured*, not assumed.

## Why v1's data had to go

v1's `jobs/build_authentic_dataset.py` generated case counts, community reports **and** the
outbreak label from one hand-written formula of weather + month + density, then trained XGBoost
on those same inputs. The model learned to copy the formula (hence ROC-AUC 0.986); it never saw a
real dengue case. Early stopping and the decision threshold were also tuned on the test set.
v2 starts again from real data.

## What data actually exists (checked October 2026)

| Source | What | Resolution | Used for |
|---|---|---|---|
| Karnataka NVBDCP *Daily Report of Dengue* (archived by ICTS Bengaluru) | Suspected, tested, positives (IgM / NS1), deaths: on the day + year-to-date | **District**, with BBMP as its own row | Target: BBMP weekly cases |
| NASA POWER daily point data | Temperature (mean/min/max), humidity, rainfall | City point | Weather features |
| Census 2011 ward abstract (v1) | Population, area, density | 198 wards (2011 delimitation) | Ward downscaling (Step 2) |
| BBMP ward boundaries (v1 GeoJSON) | Ward polygons | 243 wards (2023 delimitation) | Map; needs a crosswalk to the census wards |

**Honest resolution:** there is no public ward-level dengue data. We forecast **BBMP as a whole**
and, in Step 2, estimate ward-level risk *with uncertainty* from city-level forecasts plus ward
covariates. The map must show that uncertainty instead of pretending to be precise.

## Pipeline

```
download ──► PDFs ──► rule-based parser ─┐
                    └► LLM extractor ─────┼─► validator ─► reconciler ─► bulletin_rows.csv
                                          │                               │
hand-labelled gold set ◄── label tool     │                               ├─► bbmp_weekly_cases.csv
          │                               │                               │
          └──────────► eval ──► docs/v2/extraction_eval.md                └─► weather_weekly.csv
```

* **Rule-based parser** (`pipeline/extract/text_parser.py`): rebuilds text lines from word
  positions, separates the dengue table from the chikungunya table by title position, and picks
  the reading of each row that passes arithmetic checks (IgM + NS1 = Total, Total ≤ Samples).
  Handles real-world mess: rows that lost their label, cumulative numbers on a separate line.
* **LLM extractor** (`pipeline/extract/llm_extractor.py`): layout-preserved text → strict JSON,
  cached by (PDF hash, prompt version, model) so results are reproducible and re-runs are free.
* **Validator** (`pipeline/validate/checks.py`): row checks + whole-bulletin checks (state total
  vs sum of districts, date printed vs file date).
* **Reconciler** (`pipeline/build/reconcile.py`): picks one value per bulletin and area, with
  provenance (`extractor`, `trusted`, `agree`, `flags`).
* **Weekly series** (`pipeline/build/series.py`): uses the *cumulative* count, so missing bulletin
  days don't lose cases; removes values that break monotonicity, and chains years across the
  1 January reset.
* **Evaluation** (`pipeline/eval/`): you label ~40 bulletins by hand; the report gives accuracy and
  coverage per field and extractor, plus whether the validator's "trusted" rows really are more
  accurate.

## How to run (on your Mac, needs internet)

```bash
git checkout v2
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-pipeline.txt

python -m pipeline download --start 2022-01-01      # polite: 1 request/second, resumable
python -m pipeline status
python -m pipeline extract                          # rule-based
python -m pipeline extract --llm                    # + LLM (uses OPENROUTER_API_KEY from backend/.env)
python -m pipeline label --n 40                     # ~1 hour of hand-labelling: the ground truth
python -m pipeline build                            # reconcile + weekly series + weather
python -m pipeline eval                             # writes docs/v2/extraction_eval.md
python -m pipeline fetch-weather --start 2025-01-01 # extend weather past 2024
pytest pipeline/tests -q
```

After `eval`, re-run `build --prefer llm` if the LLM turns out more accurate.

## What to put on your resume from this step (fill in real numbers)

> Built a document-AI pipeline that extracts ___ daily government dengue bulletins (2022–2025) into a
> validated time series; hand-labelled ___ bulletins as ground truth: rule-based parser ___% vs LLM ___%
> field accuracy, and the validator's trusted rows were ___% accurate vs ___% for flagged rows.

## Known risks to check with real data

* Some bulletins may lack BBMP's cumulative numbers (seen in one 2024 sample). If that turns out to
  be common, add a fallback that builds weekly counts from the "on the day" numbers, and report coverage.
* Positives are lab-confirmed cases reported to the public system; private-lab and unreported cases
  are missing, so the series undercounts true infections. Forecasts are of *reported* cases.
* How far back the archive goes is unknown until the download runs; the manifest records every date.
