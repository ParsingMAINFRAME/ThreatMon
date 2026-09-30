import { ConsoleShell } from "@/components/ConsoleShell";
import { NewsMonitor } from "@/components/NewsMonitor";
import { RefreshButton } from "@/components/RefreshButton";
import { getNews } from "@/lib/api";
import type { NewsResponse } from "@/lib/news-types";

export const dynamic = "force-dynamic";

async function loadNews(edition: "demo" | "snapshot"): Promise<NewsResponse | null> {
  try { return await getNews(edition); }
  catch { return null; }
}

export default async function NewsPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const params = await searchParams;
  const edition = params.edition === "demo" ? "demo" : "snapshot";
  const data = await loadNews(edition);
  const mode = data ? data.edition === "demo" ? "demo" : data.events.length ? "live" : "empty" : "unavailable";
  return (
    <ConsoleShell mode={mode} section="news">
      {data ? <NewsMonitor data={data} /> : <section className="service-error">
        <p className="section-kicker">NEWS COVERAGE / CONNECTION</p>
        <h1>The news map is unavailable.</h1>
        <p>The stored coverage could not be loaded. Refresh once the data service is available.</p>
        <RefreshButton />
      </section>}
    </ConsoleShell>
  );
}
