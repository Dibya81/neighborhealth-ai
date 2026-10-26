import Link from "next/link";

import { Notice } from "@/components/ui/primitives";

export interface LegalSection { title: string; paragraphs?: string[]; bullets?: string[] }

export function LegalPage({ title, intro, sections }: { title: string; intro: string; sections: LegalSection[] }) {
  return (
    <article className="mx-auto max-w-[760px] px-4 py-12 md:px-6 md:py-16">
      <h1 className="text-balance text-4xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-4 text-lg text-muted">{intro}</p>
      <div className="mt-8">
        <Notice tone="warn" title="Pilot draft">
          This text describes what the service really does today. It is a draft for the student pilot and is being reviewed; contact details and a retention period will be added before any public launch.
        </Notice>
      </div>
      <div className="mt-12 space-y-10">
        {sections.map((s) => (
          <section key={s.title}>
            <h2 className="text-xl font-semibold tracking-tight">{s.title}</h2>
            {s.paragraphs?.map((p) => <p key={p} className="mt-3 leading-relaxed text-muted">{p}</p>)}
            {s.bullets && <ul className="mt-3 list-disc space-y-2 pl-5 leading-relaxed text-muted">{s.bullets.map((b) => <li key={b}>{b}</li>)}</ul>}
          </section>
        ))}
      </div>
      <p className="mt-14 border-t border-line pt-6 text-sm text-muted">
        See also <Link href="/privacy" className="font-medium text-lake underline underline-offset-2 hover:no-underline">privacy notice</Link>, <Link href="/terms" className="font-medium text-lake underline underline-offset-2 hover:no-underline">terms of use</Link> and <Link href="/methodology" className="font-medium text-lake underline underline-offset-2 hover:no-underline">how it works</Link>.
      </p>
    </article>
  );
}

export const PRIVACY: { title: string; intro: string; sections: LegalSection[] } = {
  title: "Privacy notice",
  intro: "NeighborHealth is a student public-health project. It is not a government service and not a medical service. This page says what we collect, why, and how you stay in control.",
  sections: [
    {
      title: "What we collect, and why",
      bullets: [
        "Your email, a password (stored only as a salted hash), an optional name, and your language: to run your account.",
        "Places you save (home, office, school) and how you want to be alerted (email, SMS or WhatsApp, including a phone number): to send you dengue-risk alerts for those places.",
        "Reports of mosquito-breeding spots: a photo, the GPS location, a category and a note. So the health team can check and clear the spot, and to show hotspot areas.",
        "Questions you ask the assistant: to answer you and to measure answer quality.",
        "Simple usage events (which page was opened) and your consent choices: to see whether the pilot works and to record what you agreed to.",
      ],
      paragraphs: ["We do not collect health records, symptoms or diagnoses. We do not run ads and we do not sell data."],
    },
    {
      title: "Who can see it",
      bullets: [
        "Health-team staff see the reports they review, including the photo and location.",
        "Other residents see approximate public report locations (to about 100 metres), never your name, email or photo.",
        "The project team sees usage in aggregate.",
      ],
    },
    {
      title: "Photos",
      paragraphs: ["We remove the camera's hidden location and device data (EXIF) from every photo before saving it. We do not yet blur faces or number plates automatically, so please photograph the water or container and keep people and vehicles out of the frame."],
    },
    {
      title: "Who else handles your data",
      bullets: [
        "Email, SMS and WhatsApp delivery: your address or number and the alert text pass through our email provider and Twilio, if you choose those channels.",
        "The assistant: if the AI writing step is switched on, your question text (not your name or email) is sent to an AI service so it can phrase an answer from official guidelines.",
        "Maps: nearby-hospital lookups use a copy of OpenStreetMap data stored on our server. Your location is not sent to OpenStreetMap.",
      ],
    },
    {
      title: "How long we keep it",
      paragraphs: ["Until you delete it. There is no automatic expiry yet; a retention period will be set and published here before any public launch."],
    },
    {
      title: "Your choices",
      bullets: [
        "Stop alerts: every email has a one-click unsubscribe link, and you can reply STOP to an SMS or WhatsApp alert. You can also remove a saved place on the Alerts page.",
        "See your data: we can give you a download of everything we hold about you.",
        "Delete everything: you can delete your account and data. This removes your account, reports and photos, saved places, alerts, consents, assistant questions and usage events. Tasks the health team already opened stay, but are no longer linked to you.",
        "Complain: contact details will be published here. In India you may also complain to the Data Protection Board under the Digital Personal Data Protection Act, 2023.",
      ],
    },
    {
      title: "Children and security",
      paragraphs: [
        "NeighborHealth is not meant for people under 18. If a parent or school wants to take part, please contact us first.",
        "Passwords are hashed, sign-in tokens expire, and sensitive actions such as deleting an account ask for your password again. No system is perfectly secure; we will tell affected people if a breach affects them.",
      ],
    },
  ],
};

export const TERMS: { title: string; intro: string; sections: LegalSection[] } = {
  title: "Terms of use",
  intro: "Please read these short terms before you use NeighborHealth.",
  sections: [
    {
      title: "This is information, not medical advice",
      paragraphs: [
        "NeighborHealth shows dengue-risk estimates and answers questions from official guidelines (WHO and the Government of India). It cannot tell you whether you have dengue.",
        "If you have severe stomach pain, repeated vomiting, bleeding, difficulty breathing, drowsiness or collapse, go to a hospital now or call 108. For anything else about your health, see a doctor or call 104.",
      ],
    },
    {
      title: "Estimates can be wrong, and may be old",
      paragraphs: [
        "Forecasts are of reported cases for the whole of BBMP. Ward-level numbers are model estimates, not counted cases, and always come with a range.",
        "The bulletins this service learns from currently end on 4 November 2024. Every page shows the date of the data behind it. Do not treat a forecast as current if it says its data is old.",
      ],
    },
    { title: "Not an emergency service", paragraphs: ["Alerts and reports are not monitored around the clock."] },
    {
      title: "Reports",
      paragraphs: ["Only report real mosquito-breeding spots. Do not include people, faces, number plates or private property you have no right to photograph. Fake or abusive reports may be removed and accounts closed. You keep ownership of your photos and allow us to use them to verify the report and, without your name, to show hotspots."],
    },
    {
      title: "Your account and alerts",
      paragraphs: ["Keep your password private. You can delete your account at any time. Alerts can be stopped at any time, and we try not to send more than two a week per person."],
    },
    {
      title: "No guarantee",
      paragraphs: ["The service is provided as it is, may be unavailable, and is run by volunteers. To the extent the law allows, we are not liable for decisions made on the basis of its estimates."],
    },
    { title: "Changes", paragraphs: ["If we change these terms or what we collect, we will tell you in the app and ask again where the law requires."] },
  ],
};
