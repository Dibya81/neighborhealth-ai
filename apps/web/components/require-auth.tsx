"use client";

import { Lock, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useApp } from "@/components/providers";
import { Button, Panel, Skeleton } from "@/components/ui/primitives";

export function RequireAuth({ children, roles, reason }: { children: React.ReactNode; roles?: string[]; reason: string }) {
  const { user, authReady } = useApp();
  const pathname = usePathname();
  if (!authReady) return <Skeleton className="h-44" />;
  if (!user) {
    return (
      <Panel className="max-w-xl p-6 md:p-8">
        <span className="grid h-10 w-10 place-items-center rounded bg-lake-soft text-lake"><Lock className="h-5 w-5" /></span>
        <h2 className="mt-5 text-xl font-semibold tracking-tight">Sign in to continue</h2>
        <p className="mt-2 text-muted">{reason}</p>
        <Link href={`/login?next=${encodeURIComponent(pathname)}`} className="mt-6 inline-block"><Button size="lg">Sign in or create an account</Button></Link>
      </Panel>
    );
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <Panel className="max-w-xl p-6 md:p-8">
        <span className="grid h-10 w-10 place-items-center rounded bg-sunken text-muted"><ShieldAlert className="h-5 w-5" /></span>
        <h2 className="mt-5 text-xl font-semibold tracking-tight">This area is for the health team</h2>
        <p className="mt-2 text-muted">Your account doesn&apos;t have access. If you work with BBMP health, ask an administrator to give you the health team role.</p>
      </Panel>
    );
  }
  return <>{children}</>;
}
