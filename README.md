# NeighborHealth 2.0

**Dengue early warning for Bengaluru, built on real surveillance data, with honest uncertainty.**

NeighborHealth turns the Karnataka health department's daily dengue bulletins (PDFs) into a weekly
case series for BBMP, forecasts the next 1–4 weeks with calibrated prediction intervals, estimates
ward-level risk with its uncertainty, and gives residents and health officials tools to act on it:
citizen reports with photo checks, alerts in Kannada/Hindi/English, a guideline-grounded assistant,
and an officials' dashboard with route optimisation.

> v1 (first semester) trained on synthetic labels generated from the same features the model used, so
> its reported accuracy was meaningless. v2 starts again from real data and measures everything.
> See `docs/v2/STEP1_DATA.md` for that story.

## What's inside

| Step | What it does | Where |
|---|---|---|
| 1. Real data | Downloads NVBDCP bulletins, extracts tables with a rule-based parser **and** an LLM, validates the arithmetic, reconciles, and measures accuracy against hand-labelled bulletins | `pipeline/` |
| 2. Forecasting ML | Baselines (persistence, seasonal naive) → SARIMA (Fourier) → Poisson GLM → gradient boosting → ensemble. Rolling-origin backtests, online conformal intervals, WIS, SHAP explanations, ward downscaling with Monte Carlo uncertainty | `ml/` |
| 3. Citizen reports | Photo + GPS, zero-shot CLIP check, perceptual-hash duplicate merging, spam rules, Beta trust scores, DBSCAN hotspots | `apps/api/app/services/reports.py`, `hotspots.py`, `vision.py` |
| 4. Officials' tools | Overview, review queue, task lifecycle with audit trail, OR-Tools vehicle routing (heuristic fallback) | `apps/api/app/routers/officials.py`, `services/routing.py`, `services/tasks.py` |
| 5. Alerts | Saved places → wards, hysteresis, de-duplication, quiet hours, fatigue cap, Redis Streams queue, WhatsApp/SMS/email in en/kn/hi, fatigue metrics | `apps/api/app/services/alerts/` |
| 6. Assistant | BM25 retrieval over WHO/NCVBDC/ICMR documents, citations, no diagnosis, warning-sign escalation; ward explanations from SHAP only, with a fact-checking verifier | `apps/api/app/services/assistant/` |
| 7. Production | PostGIS, Docker Compose, CI with tests + model quality gate, weekly retrain workflow, file registry (+ MLflow), PSI drift checks, JWT auth with roles, Prometheus metrics, JSON logs, config-driven city | `docker-compose.yml`, `.github/workflows/`, `config/cities/` |
| 8. Real users | Group codes for RWAs, consent records, privacy-safe analytics, pilot metrics dashboard, outreach playbook | `apps/api/app/services/pilot.py`, `docs/v2/PILOT_PLAYBOOK.md` |
| Web app | Next.js 14 + TypeScript: forecast fan chart with rainfall, ward map with uncertainty shading, report flow, alerts, assistant, officials' dashboard, offline-capable PWA, three languages, dark mode | `apps/web/` |

## Architecture

```
NVBDCP PDFs ─► pipeline (download → extract ×2 → validate → reconcile → weekly series) ─┐
NASA POWER ──► weekly weather ───────────────────────────────────────────────────────────┤
                                                                                         ▼
                         ml (backtest all models → choose → registry/promote → publish latest.json)
                                                                                         │
             ┌───────────────────────── FastAPI (apps/api) ◄─────────────────────────────┘
             │  forecast & wards · reports · officials · alerts engine · assistant · pilot
             │        │                     │                      │
        PostGIS / SQLite         Redis Streams ─► alerts worker ─► WhatsApp / SMS / email
             │
        Next.js web app (apps/web) ── residents + health officials
```

## Run it

```bash
git checkout v2
python3 -m venv .venv && source .venv/bin/activate
make setup                     # Python + web dependencies, creates .env files
# put OPENROUTER_API_KEY etc. in apps/api/.env

make data                      # Step 1: real bulletins + weather -> weekly series
python -m pipeline label --n 40 && python -m pipeline eval   # measure extraction accuracy
make weekly                    # Step 2: backtest, promote, publish forecast, evaluate alerts
make guidelines clinics        # Step 6 sources + nearby facilities

make api                       # http://localhost:8000/docs
make web                       # http://localhost:3000
make worker                    # alert delivery (dry-run by default)
make officials EMAIL=you@x.com PASSWORD=...
```

Or everything in containers: `docker compose up --build`, then
`docker compose run --rm api python -m ml weekly`.

## Results (fill in after running; never typed by hand elsewhere)
- Extraction accuracy: `docs/v2/extraction_eval.md`
- Forecast skill vs baselines, interval coverage: `docs/v2/MODEL_CARD.md`
- Explanation faithfulness: `docs/v2/explanation_eval.md`
- Pilot outcomes: `docs/v2/PILOT_PLAYBOOK.md`

## Data sources
Karnataka NVBDCP daily dengue bulletins (archived by ICTS Bengaluru) · NASA POWER · Census of India 2011 ·
BBMP ward boundaries · WHO, NCVBDC and ICMR guidance · © OpenStreetMap contributors (ODbL).
Forecasts are of reported cases and are not medical advice.
