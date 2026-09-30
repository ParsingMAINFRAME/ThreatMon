"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

export function RefreshButton() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  return <button type="button" className="refresh-control" disabled={pending} aria-label={pending ? "Refreshing records" : "Refresh records"} onClick={() => startTransition(() => router.refresh())}><span aria-hidden="true">{pending ? "…" : "↻"}</span><span>{pending ? "Refreshing" : "Refresh"}</span></button>;
}
