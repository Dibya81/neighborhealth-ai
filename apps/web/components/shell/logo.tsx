export function Logo({ className = "h-7 w-7" }: { className?: string }) {
  // A drop of standing water and its ripples: where dengue starts.
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#14213D" />
      <path d="M16 6.5c-2.6 3.8-5.4 7.3-5.4 10.4a5.4 5.4 0 0 0 10.8 0c0-3.1-2.8-6.6-5.4-10.4Z" fill="#F2B33D" />
      <path d="M7.5 24.5c2.4 1.3 5.3 2 8.5 2s6.1-.7 8.5-2" stroke="#40BAB4" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </svg>
  );
}
