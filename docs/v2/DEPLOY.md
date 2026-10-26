# Deploying NeighborHealth 2.0

**Read this first.** The real bulletin archive ends on **2024-11-04**, so every forecast this system can
produce today describes November 2024. `/health` reports `degraded` for that reason and the alert engine refuses to
send anything from a forecast older than 21 days. Deploying is fine for a **demo or for testing the workflow with
real people using dry-run alerts**. Do **not** switch alerts to live (`ALERTS_DRY_RUN=false`) or call the forecast
"current" until a live data source exists and `/health` is `ok`.

Nothing here was tested on a hosting provider (needs your accounts); the containers and the local stack are what was verified.

## What runs

| Part | Image / service | Notes |
|---|---|---|
| API | `apps/api/Dockerfile` | FastAPI, port 8000, runs DB migrations on start |
| Alerts worker | same image, command `python -m app.services.alerts.worker` | needs the same env + Redis |
| Database | Postgres 16 with PostGIS | SQLite works for a single-instance demo |
| Queue | Redis | optional in dev (in-memory), **required** with more than one worker |
| Web | `apps/web/Dockerfile` (or Vercel) | **not built or reviewed yet** (UI pass pending) |

The API image carries the real weekly series as a seed: an empty data volume is filled on first start.

## Environment variables (API and worker)

| Variable | Set to |
|---|---|
| `APP_ENV` | `production` (refuses to start with the default `JWT_SECRET`) |
| `JWT_SECRET` | long random string, e.g. `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | `redis://host:6379/0` |
| `ALLOWED_ORIGINS` | your web origin(s), comma separated, `https://...` |
| `PUBLIC_WEB_URL` / `PUBLIC_API_URL` | public https addresses (used in alert links, unsubscribe links, Twilio signature check) |
| `ALERTS_DRY_RUN` | `true` until the checklist below is done |
| `OPENROUTER_API_KEY` | optional; without it the assistant shows the best matching official passages verbatim |
| `TWILIO_*`, `SMTP_*` | only when going live with alerts |

## First start

```bash
# 1. build the images and start everything locally (or the same commands on your host)
docker compose up --build

# 2. publish a forecast from the seeded data (no download needed)
docker compose run --rm api python -m ml weekly --no-download

# 3. build the assistant's guideline index (downloads WHO + NCVBDC documents)
docker compose run --rm api python -m app.services.assistant.corpus fetch

# 4. create a health-team account
docker compose run --rm api python -m app.cli create-user --email you@example.org --password '...' --role official
```

Open `http://localhost:8000/docs`, and `/health` (it will say `degraded`, honestly).

## Hosting (any container host: Render, Fly.io, Railway, ...)
1. Create Postgres (with PostGIS) and Redis; copy their URLs into the env above.
2. Deploy the API image, then the worker image with the worker command. Give both the same env and a **persistent disk**
   at `/repo/data/v2` (uploaded report photos, forecasts and the guideline index live there).
3. Put the API behind HTTPS on your domain and set `PUBLIC_API_URL` to it.
4. Deploy the web app (Vercel works for `apps/web`; set `NEXT_PUBLIC_API_URL`) once the UI pass is done.
5. Run steps 2-4 above on the deployed API.

## Before real alerts (all of these)
- [ ] A live data source exists and `/health` returns `ok`.
- [ ] Kannada/Hindi text reviewed (`docs/v2/TRANSLATION_REVIEW.md`).
- [ ] Privacy notice and terms filled in and published (`docs/v2/legal/`).
- [ ] Twilio: WhatsApp message templates approved for messages outside the 24-hour window; inbound webhook set to
      `https://<api>/v2/webhooks/twilio`; send to your own phone first (WhatsApp sandbox, then real).
- [ ] Tested STOP and the email unsubscribe link yourself.
- [ ] Backups for Postgres and the data disk; someone owns the on-call phone number.
- [ ] Then, and only then, `ALERTS_DRY_RUN=false`.
