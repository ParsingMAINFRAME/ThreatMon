"use client";

import Link from "next/link";
import { ConsoleShell } from "@/components/ConsoleShell";

export default function ErrorBoundary({ reset }: { reset: () => void }) {
  return (
    <ConsoleShell mode="unavailable" detail>
      <section className="max-w-3xl pb-14 pt-7 sm:pb-24 sm:pt-12" aria-labelledby="error-title">
        <p className="section-kicker">View unavailable / Application error</p>
        <h1 id="error-title" className="mb-5 mt-5 text-[36px] leading-[1.12] tracking-[-.035em] sm:text-[48px]" style={{ fontFamily: "var(--serif)" }}>This view could not load.</h1>
        <p className="max-w-md text-sm leading-7 text-[color:var(--muted)]">Try loading it again. Your stored event records have not been changed.</p>
        <div className="mt-8 flex flex-wrap items-center gap-x-7 gap-y-4 border-t border-[color:var(--rule)] pt-5">
          <button onClick={reset} type="button" className="border border-[color:var(--ink)] bg-[color:var(--ink)] px-5 py-3 text-xs text-[color:var(--paper)] hover:bg-[color:var(--accent)] hover:border-[color:var(--accent)]">Try again <span aria-hidden="true" className="ml-6">↻</span></button>
          <Link href="/" className="text-xs text-[color:var(--accent)] underline decoration-[color:var(--rule)] underline-offset-4 hover:decoration-current">Return to world monitor <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </ConsoleShell>
  );
}
