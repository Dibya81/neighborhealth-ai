# Step 8: Pilot playbook (real users)

Goal for the pilot: **2–3 resident welfare associations (RWAs) or your college NSS unit, 6–8 weeks, plus one
conversation with a BBMP health officer or public-health professor.** Even "200 residents subscribed,
150 verified reports" is a strong, honest result.

## What's already built for the pilot
- **Group codes (cohorts):** each RWA gets a code (e.g. `JAYANAGAR-4T`). Residents enter it when signing up,
  or open `https://<your-site>/login?group=JAYANAGAR-4T`. The Health team page shows metrics per group.
- **Consent records:** terms, alerts and optional research consent are stored with a version (`consents` table).
- **Privacy-safe analytics:** only whitelisted events (`page_view`, `report_submitted`, ...) with no personal data.
- **Pilot metrics:** *Health team → Pilot*: residents, subscribers, weekly active users, reports, verified
  reports, tasks completed, assistant grounding rate, alert usefulness and the alert-fatigue index.

## Before launch: checklist
- [ ] Forecast published and the quality gate passes (`python -m ml gate`).
- [ ] Extraction accuracy measured (`docs/v2/extraction_eval.md`).
- [ ] Kannada and Hindi text reviewed by native speakers (`apps/web/lib/i18n.ts`, `apps/api/app/services/alerts/templates.py`,
      `apps/api/app/services/assistant/assistant.py`).
- [ ] Guidelines downloaded and indexed (`make guidelines`); ask 20 test questions, check every citation by hand.
- [ ] Alerts tested in dry-run (`ALERTS_DRY_RUN=true`, see `data/v2/outbox.log`), then with your own phone.
- [ ] At least one official account created (`make officials EMAIL=... PASSWORD=...`).
- [ ] Privacy notice and terms: drafts are in `docs/v2/legal/`; fill the ▢ blanks, get them reviewed, and publish them in the web app.
- [ ] If you publish results, check with your college whether ethics/IRB approval is needed for user research.

## Week by week
| Week | What happens |
|---|---|
| 0 | Meet RWA committee / NSS coordinator. 15-minute demo. Agree on a group code and one contact person. |
| 1 | Onboarding session (in person or WhatsApp group): sign up, save home, report one spot together. |
| 2–6 | Weekly forecast + alerts run. Health-team account reviews reports within 48 h. Short weekly WhatsApp update to the group. |
| 3 | 5-minute feedback survey (below). Fix the top 3 issues. |
| 6 | Second survey + 3 short interviews. Export metrics. Write the pilot report. |
| 7 | Share results with the RWA and the BBMP/public-health contact. |

## Outreach templates (edit names, keep it short)

**To an RWA secretary (email / WhatsApp)**
> Namaskara! I'm <name>, a <year> engineering student at <college>. I've built NeighborHealth, a free,
> non-commercial tool that forecasts dengue risk in Bengaluru from government health bulletins and weather,
> and lets residents report mosquito breeding spots and get a message when risk rises near their homes.
> I'd love to run a 6-week pilot with <RWA name>: a 15-minute demo for the committee and one short
> session for residents. No cost, no ads, and residents can delete their data at any time.
> Could I show it to you this week? Demo: <link>

**To your college NSS coordinator**
> Sir/Madam, I'd like to propose a dengue-awareness NSS activity: volunteers use the NeighborHealth app
> to survey and report breeding spots around campus and nearby wards for 6 weeks, and we share the
> verified findings with BBMP's ward health officers. It needs about 2 hours per volunteer per week.
> I can present the plan at the next NSS meeting.

**To a BBMP ward health officer / public-health professor**
> I've built a prototype that turns the daily Karnataka NVBDCP dengue bulletins into a weekly BBMP
> forecast with uncertainty, and gives health teams a queue of photo-verified citizen reports and
> optimised inspection routes. I'd value 20 minutes of your feedback on whether this would be useful
> in the field and what's missing. Model accuracy and limitations: <link to /forecast and /methodology>.

## Feedback survey (5 questions, ~3 minutes)
1. How easy was it to find the dengue risk for your area? (1–5)
2. Did an alert make you do anything (empty water, tell neighbours, see a doctor)? (yes / no / no alert yet)
3. How many alerts would be too many per month? (1 / 2 / 4 / more)
4. Was the language right for you? Which language do you prefer?
5. What one thing should we change?

## Pilot report: numbers to fill in (and put on your resume)
- Residents registered / subscribed / weekly active
- Reports submitted / verified / median time to review / tasks cleared
- Alerts sent per user per week, % rated useful, unsubscribe rate after an alert
- Assistant questions, % answered from sources, citation accuracy from your manual check
- One quote from a resident and one from an official (with permission)

## Data deletion
Users can delete their own account (`DELETE /v2/auth/me`, asks for their password) and download their data
(`GET /v2/auth/me/export`). This removes the account, reports and photo files, saved places, alerts, consents,
assistant questions and usage events; field tasks already opened stay but are unlinked from the person
(see `app/services/privacy.py`). If someone asks by message instead, ask them to do it in the app, or use
`python -c "from app.services.privacy import delete_user_data; ..."` from `apps/api` after verifying who they are.
Privacy notice and terms drafts: `docs/v2/legal/` (fill the ▢ blanks first).
