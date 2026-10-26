import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-4 py-24 text-center">
      <h1 className="font-display text-3xl font-semibold">This page doesn&apos;t exist</h1>
      <p className="mt-3 text-muted">The link may be old. The risk map is a good place to start.</p>
      <Link href="/map" className="mt-6 inline-block rounded bg-lake px-4 py-2.5 text-sm font-medium text-white">Open the risk map</Link>
    </div>
  );
}
