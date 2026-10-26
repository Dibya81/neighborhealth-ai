import Link from "next/link";

export const metadata = { title: "How it works" };

const STEPS = [
  {
    title: "Real surveillance data",
    body: "Every day Karnataka's vector-borne disease programme publishes a dengue bulletin as a PDF. We read those PDFs with two independent extractors (a rule-based parser and an AI reader), check the arithmetic in every row, and measure accuracy against bulletins checked by hand. The result is a weekly count of lab-confirmed cases reported for BBMP.",
  },
  {
    title: "Weather that matters to mosquitoes",
    body: "Rain fills containers; warm, humid weeks speed up the mosquito life cycle. We use daily NASA POWER data for Bengaluru and look at the 2–8 weeks before each forecast.",
  },
  {
    title: "A forecast that's tested like it's live",
    body: "Several models compete: simple baselines (same as this week, same week last year), a seasonal time-series model, a Poisson regression, gradient boosting and an ensemble. Each is re-run week by week on past data using only what was known at the time. A model is used only if it beats the same-week-last-year baseline and its ranges are well calibrated.",
  },
  {
    title: "Ward estimates, labelled as estimates",
    body: "Official data stops at the BBMP level. To show wards, we spread the city forecast using each ward's estimated population and density, adjusted by verified citizen reports. That's why the map shows a range and fades wards where we're less sure.",
  },
  {
    title: "Explanations from the model, not imagination",
    body: "The reasons shown for a forecast come from the model itself (SHAP values). AI-written summaries may only use those numbers, and a checker rejects any text that adds a number or cause that isn't there.",
  },
  {
    title: "Retrained every week",
    body: "New bulletins arrive, the backtest runs again, and a new model replaces the old one only if it does at least as well on the same data. Every version is kept so we can roll back.",
  },
];

export default function Methodology() {
  return (
    <article className="mx-auto max-w-[820px] px-4 py-10 md:px-6 md:py-14">
      <h1 className="font-display text-4xl font-semibold tracking-tight">How NeighborHealth works</h1>
      <p className="mt-4 max-w-prose text-lg text-muted">
        We forecast reported dengue cases for Bengaluru one to four weeks ahead, and we try hard to show how sure we are. This is a public-health aid, not a diagnosis tool.
      </p>
      <ol className="mt-12 space-y-10">
        {STEPS.map((s, i) => (
          <li key={s.title} className="grid grid-cols-[2.5rem_1fr] gap-4">
            <span className="tnum font-display text-2xl font-semibold text-[#E06A2C]">{i + 1}</span>
            <div>
              <h2 className="text-lg font-semibold">{s.title}</h2>
              <p className="mt-2 max-w-prose leading-relaxed text-muted">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>
      <section className="mt-14 border-t border-line pt-8">
        <h2 className="text-lg font-semibold">Limits you should know</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-muted">
          <li>Counts are reported, lab-confirmed cases. Many infections are never tested, and testing levels change.</li>
          <li>Weather comes from a single point for the whole city.</li>
          <li>Ward numbers are model estimates, not counts from the ward.</li>
        </ul>
        <p className="mt-6 text-sm text-muted">
          See the live accuracy numbers on the <Link href="/forecast" className="text-lake underline-offset-2 hover:underline">forecast page</Link>. Sources: Karnataka NVBDCP daily bulletins via the ICTS Bengaluru archive, NASA POWER, Census of India 2011, BBMP ward boundaries, WHO and NCVBDC guidelines, © OpenStreetMap contributors.
        </p>
      </section>
    </article>
  );
}
