import Link from "next/link";
import { ConsoleShell } from "@/components/ConsoleShell";

export default function NotFound() {
  return (
    <ConsoleShell mode="empty" detail>
      <section className="max-w-3xl pb-14 pt-7 sm:pb-24 sm:pt-12" aria-labelledby="not-found-title">
        <p className="section-kicker">Record lookup / 404</p>
        <h1 id="not-found-title" className="mb-5 mt-5 text-[36px] leading-[1.12] tracking-[-.035em] sm:text-[48px]" style={{ fontFamily: "var(--serif)" }}>Event not found.</h1>
        <p className="max-w-md text-sm leading-7 text-[color:var(--muted)]">This record may have been removed or its link may be incorrect. The event register lists the records currently available.</p>
        <div className="mt-8 border-t border-[color:var(--rule)] pt-5">
          <Link href="/signals#event-register" className="inline-flex items-center gap-8 border border-[color:var(--ink)] bg-[color:var(--ink)] px-5 py-3 text-xs text-[color:var(--paper)] hover:bg-[color:var(--accent)] hover:border-[color:var(--accent)]">Return to event register <span aria-hidden="true">→</span></Link>
        </div>
      </section>
    </ConsoleShell>
  );
}
