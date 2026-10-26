import { ArrowRight } from "lucide-react";
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-24 md:py-32">
      <p className="num text-6xl font-semibold text-lake">404</p>
      <h1 className="mt-4 text-balance text-3xl font-semibold tracking-tight">This page doesn&apos;t exist</h1>
      <p className="mt-3 text-lg text-muted">The link may be old, or mistyped. These are good places to start.</p>
      <ul className="mt-8 divide-y divide-line border-y border-line">
        {[["/map", "Open the risk map"], ["/forecast", "See the city forecast"], ["/assistant", "Ask about dengue"]].map(([href, label]) => (
          <li key={href}>
            <Link href={href} className="group flex min-h-[56px] items-center justify-between gap-4 text-base font-medium transition-colors hover:text-lake">
              {label}<ArrowRight className="h-4 w-4 text-muted transition-transform group-hover:translate-x-1 group-hover:text-lake" aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
