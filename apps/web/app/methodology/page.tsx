import { Clock } from "lucide-react";
import Link from "next/link";

export const metadata = { title: "How it works" };

const STEPS = [
  {
    title: "Real surveillance data, checked",
    body: "Every day Karnataka's vector-borne disease programme publishes a dengue bulletin as a PDF. We read the district table in each one. Newer bulletins are scanned images, so we read the key rows with text recognition and accept a reading only if the arithmetic works (for example, positives found by two tests must add up to the total). When we add up the 30 districts in a bulletin, they match the printed state total in 374 of 379 readable bulletins. We also compared our yearly totals with the Ministry's own table: they agree within about 5% for 2021, 2022 and 2024, but our 2023 totals sit about 13% lower, so treat 2023 as a minimum.",
  },
  {
    title: "Weather that matters to mosquitoes",
    body: "Rain fills containers, and warm, humid weeks speed up the mosquito life cycle. We use daily NASA POWER weather for Bengaluru and look at the 2 to 8 weeks before each forecast. It is one weather point for the whole city.",
  },
  {
    title: "A forecast that is tested as if it were live",
    body: "Several methods compete: simple baselines (same as this week, same week last year), a seasonal time-series model, a Poisson regression, gradient boosting and a blend of them. Each is re-run week by week on past data, using only what was known at the time, and judged only on weeks that have real bulletins. Ranges (50, 80 and 95%) come from the method's own past errors.",
  },
  {
    title: "What the tests show, honestly",
    body: "With about three years of usable history, the forecast beats the 'same week last year' baseline one and two weeks ahead, and does not beat it three or four weeks ahead. The live accuracy table on the forecast page is generated from the same tests, so it cannot drift from the truth.",
  },
  {
    title: "Ward estimates, labelled as estimates",
    body: "Official data stops at the BBMP level. To show wards, we share the city forecast out using each ward's estimated population and density, adjusted by verified citizen reports. Wards therefore differ only a little, which is why the map offers a 'Compare wards' view, shows a range, and fades wards where we are less sure.",
  },
  {
    title: "Explanations come from the model",
    body: "The reasons shown for a forecast come from the model itself (SHAP values). Written summaries may only use those numbers, and a checker rejects any text that adds a number or a cause that is not there.",
  },
  {
    title: "Keeping it current",
    body: "When new bulletins arrive, every method is tested again, and a new model replaces the old one only if it does at least as well on the same data. That weekly update is paused for now (see above), because there are no newer bulletins to learn from.",
  },
];

export default function Methodology() {
  return (
    <article className="mx-auto max-w-[820px] px-4 py-12 md:px-6 md:py-16">
      <h1 className="text-balance text-4xl font-semibold tracking-tight md:text-5xl">How NeighborHealth works</h1>
      <p className="text-pretty mt-5 max-w-prose text-lg text-muted">
        We forecast reported dengue cases for Bengaluru one to four weeks ahead, and we work hard to show how sure we are. This is a public-health aid, not a diagnosis tool.
      </p>

      <section id="data" className="mt-12 scroll-mt-24 rounded-lg border border-warn-line bg-warn-bg p-6 text-warn-ink md:p-8">
        <h2 className="flex items-center gap-2.5 text-xl font-semibold text-warn-ink"><Clock className="h-5 w-5" aria-hidden />Why you see &ldquo;archived data&rdquo;</h2>
        <p className="mt-3 leading-relaxed">
          The public archive of daily bulletins that this site is built on stops on <strong className="font-semibold">4 November 2024</strong>. There is nothing newer to learn from, so every forecast, ward estimate and chart here describes that time, not today.
        </p>
        <ul className="mt-4 list-disc space-y-1.5 pl-5">
          <li>Alerts are paused: no message is sent from an old forecast.</li>
          <li>The map and forecast are useful for seeing how the system works, and how past seasons looked.</li>
          <li>Do not use this site to decide anything about this week. For health advice, see a doctor or call 104.</li>
        </ul>
      </section>

      <ol className="mt-14 space-y-12">
        {STEPS.map((s, i) => (
          <li key={s.title} className="grid grid-cols-[2.5rem_1fr] gap-4">
            <span className="num pt-0.5 text-2xl font-semibold text-lake">{i + 1}</span>
            <div>
              <h2 className="text-xl font-semibold tracking-tight">{s.title}</h2>
              <p className="mt-2.5 max-w-prose leading-relaxed text-muted">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <section className="mt-16 border-t border-line pt-10">
        <h2 className="text-xl font-semibold tracking-tight">Limits you should know</h2>
        <ul className="mt-4 list-disc space-y-2.5 pl-5 text-muted">
          <li>Counts are reported, lab-confirmed cases. Many infections are never tested, and testing levels change.</li>
          <li>Weather comes from a single point for the whole city.</li>
          <li>Ward numbers are model estimates, not counts from the ward.</li>
          <li>Three years of history is short, so ranges are wide.</li>
        </ul>
        <p className="mt-8 max-w-prose text-sm leading-relaxed text-muted">
          See the live accuracy numbers on the <Link href="/forecast" className="font-medium text-lake underline underline-offset-2 hover:no-underline">forecast page</Link>, and read our <Link href="/privacy" className="font-medium text-lake underline underline-offset-2 hover:no-underline">privacy notice</Link> and <Link href="/terms" className="font-medium text-lake underline underline-offset-2 hover:no-underline">terms</Link>.
          Sources: Karnataka NVBDCP daily bulletins via the ICTS Bengaluru archive, NASA POWER, Census of India 2011, BBMP ward boundaries, WHO and NCVBDC guidelines, © OpenStreetMap contributors.
        </p>
      </section>
    </article>
  );
}
