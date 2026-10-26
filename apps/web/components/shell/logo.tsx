export function Logo({ className = "h-8 w-8" }: { className?: string }) {
  // A drop of standing water and its ripple: where dengue starts.
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <rect width="32" height="32" rx="8" fill="#0E1A2B" />
      <path d="M16 6c-2.7 3.9-5.6 7.4-5.6 10.6a5.6 5.6 0 0 0 11.2 0C21.6 13.4 18.7 9.9 16 6Z" fill="#FFFFFF" />
      <path d="M8 25c2.3 1.2 5 1.8 8 1.8s5.7-.6 8-1.8" stroke="#56C8C2" strokeWidth="1.75" fill="none" strokeLinecap="round" />
    </svg>
  );
}
