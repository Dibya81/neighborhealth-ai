"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useApp } from "@/components/providers";
import { Button, Skeleton } from "@/components/ui/primitives";

export function RequireAuth({ children, roles, reason }: { children: React.ReactNode; roles?: string[]; reason: string }) {
  const { user, authReady } = useApp();
  const pathname = usePathname();
  if (!authReady) return <Skeleton className="h-40" />;
  if (!user) {
    return (
      <div className="rounded-lg border border-line bg-surface p-6">
        <p className="font-medium">Sign in to continue</p>
        <p className="mt-1 text-sm text-muted">{reason}</p>
        <Link href={`/login?next=${encodeURIComponent(pathname)}`} className="mt-4 inline-block"><Button>Sign in or create an account</Button></Link>
      </div>
    );
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <div className="rounded-lg border border-line bg-surface p-6">
        <p className="font-medium">This area is for the health team</p>
        <p className="mt-1 text-sm text-muted">Your account doesn&apos;t have access. Ask an administrator if you work with BBMP health.</p>
      </div>
    );
  }
  return <>{children}</>;
}
