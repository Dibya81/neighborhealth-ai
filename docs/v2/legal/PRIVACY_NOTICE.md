# NeighborHealth privacy notice

*Draft for the student pilot. Fill in the two blanks marked ▢ and have your college or a lawyer read it
before you invite the public. Last updated: ▢ date.*

**Who is responsible for your data:** ▢ your name, ▢ contact email. NeighborHealth is a student public-health
project, not a government service and not a medical service.

## What we collect, and why

| What | Why | Who can see it |
|---|---|---|
| Email, password (stored only as a salted hash), name (optional), language | To run your account | You. Health-team staff see your name and report history only where needed to review a report. |
| Places you save (home, office, school) and how you want to be alerted (email, SMS, WhatsApp, phone number) | To send you dengue-risk alerts for those places | You, and the systems that deliver the message (below). |
| Reports of mosquito-breeding spots: photo, GPS location, category, note | So the health team can check and clear the spot, and to show hotspot areas | Health-team staff. Other residents see approximate public report locations, **never your name, email or photo**. |
| Questions you ask the assistant | To answer you and to measure answer quality | You and the project team. |
| Simple usage events (which page was opened) | To see if the pilot works | The project team, in aggregate. |
| Your consent choices | To prove what you agreed to | You and the project team. |

We do **not** collect your health records, symptoms, or diagnoses, and we do not run ads or sell data.

## Photos
We remove the camera's hidden location/device data (EXIF) from every photo before saving it. We do **not yet**
blur faces or number plates automatically, so please photograph the water, tyre or container and avoid people
and vehicles in the frame.

## Who else handles your data
* **Email / SMS / WhatsApp delivery:** your address or number and the alert text pass through our email provider
  and Twilio when you choose those channels.
* **The assistant:** if the project has switched on the AI writing step, your *question text* (not your name or
  email) is sent to an AI service (OpenRouter) so it can phrase an answer from official guidelines.
* **Maps:** nearby-hospital lookups use a copy of OpenStreetMap data stored on our server; your location is not
  sent to OpenStreetMap.

## How long we keep it
Until you delete it. There is no automatic expiry yet; ▢ decide a rule (for example, inactive accounts removed
after 12 months) and write it here before the pilot.

## Your choices
* **Stop alerts:** every email has a one-click unsubscribe link; reply **STOP** to an SMS or WhatsApp alert.
* **See your data:** `GET /v2/auth/me/export` (in the app: *Account → Download my data*).
* **Delete everything:** `DELETE /v2/auth/me` (in the app: *Account → Delete my account*). This removes your account,
  reports and photos, saved places, alerts, consents, assistant questions and usage events. Tasks the health team already
  opened from your reports stay, but are no longer linked to you. Backups, if any are made, are deleted on the
  normal backup cycle.
* **Correct your data:** edit your name/language in the app, or write to the address above.
* **Complaints:** write to the address above. In India you may also complain to the Data Protection Board
  under the Digital Personal Data Protection Act, 2023.

## Children
NeighborHealth is not meant for people under 18. If a parent or school wants to take part, contact us first.

## Security
Passwords are hashed; connections should use HTTPS in production; sign-in tokens expire; sensitive actions
(like deleting an account) ask for your password again. No system is perfectly secure; we will tell affected users
if a breach affects them.
