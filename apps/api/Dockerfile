FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/repo:/repo/apps/api
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl && rm -rf /var/lib/apt/lists/*

WORKDIR /repo
COPY requirements-pipeline.txt ./
COPY apps/api/requirements.txt apps/api/requirements.txt
RUN pip install -r apps/api/requirements.txt

COPY config ./config
COPY pipeline ./pipeline
COPY ml ./ml
COPY apps/api ./apps/api
COPY frontend/assets/bengaluru-wards.geojson ./frontend/assets/bengaluru-wards.geojson
COPY backend/data/processed/bbmp_198_wards_demographics.csv ./backend/data/processed/bbmp_198_wards_demographics.csv
COPY backend/data/raw/nasa_power_bengaluru_daily_2015_2024.json ./backend/data/raw/nasa_power_bengaluru_daily_2015_2024.json

# Real processed data (weekly series, weather) used to seed an empty data volume on first start.
COPY data/v2/processed /repo/seed/v2/processed
COPY data/v2/interim/extracted_rule.jsonl /repo/seed/v2/interim/extracted_rule.jsonl

RUN useradd -m app && mkdir -p /repo/data/v2 /repo/docs/v2 && chown -R app /repo/data /repo/docs \
    && chmod -R a+rX /repo && chmod +x /repo/apps/api/docker-entrypoint.sh   # host files may be owner-only readable
USER app
WORKDIR /repo/apps/api
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs http://localhost:8000/health || exit 1
ENTRYPOINT ["/repo/apps/api/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
