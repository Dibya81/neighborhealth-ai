# NeighborHealth 2.0, common commands (run from the repo root, with your venv active)
PY ?= python
export PYTHONPATH := $(CURDIR):$(CURDIR)/apps/api

.PHONY: setup data weekly api worker web test lint officials guidelines clinics

setup:            ## install Python + web dependencies
	$(PY) -m pip install -r apps/api/requirements.txt
	cd apps/web && npm install
	cp -n apps/api/.env.example apps/api/.env || true
	cp -n apps/web/.env.example apps/web/.env.local || true

data:             ## Step 1: download bulletins + weather, extract, build weekly series
	$(PY) -m pipeline download --start 2022-01-01
	$(PY) -m pipeline fetch-weather --start 2025-01-01
	$(PY) -m pipeline extract --llm
	$(PY) -m pipeline build

weekly:           ## The weekly loop: fresh data -> retrain/backtest -> promote -> publish -> alerts
	cd apps/api && $(PY) -m app.cli export-reports
	$(PY) -m ml weekly
	cd apps/api && $(PY) -m app.cli run-alerts

guidelines:       ## Step 6: download + index official guidelines for the assistant
	cd apps/api && $(PY) -m app.services.assistant.corpus fetch

clinics:          ## nearby facilities from OpenStreetMap
	cd apps/api && $(PY) -m app.services.clinics fetch

api:
	cd apps/api && uvicorn app.main:app --reload --port 8000

worker:
	cd apps/api && $(PY) -m app.services.alerts.worker

web:
	cd apps/web && npm run dev

officials:        ## create a health-official account: make officials EMAIL=x PASSWORD=y
	cd apps/api && $(PY) -m app.cli create-user --email $(EMAIL) --password $(PASSWORD) --role official

test:
	$(PY) -m pytest pipeline/tests ml/tests apps/api/tests -q

lint:
	ruff check pipeline ml apps/api
	cd apps/web && npm run typecheck
