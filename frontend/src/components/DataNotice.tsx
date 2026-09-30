import type { DataMode } from "@/lib/presentation";

export function DataNotice({ mode }: { mode: DataMode }) {
  const messages: Record<DataMode, string> = {
    demo: "Synthetic scenarios and illustrative map positions. No event shown here is a live alert.",
    live: "Retrieved official records. Check publication and retrieval times; source ingestion is separate from refresh.",
    mixed: "Official snapshots and synthetic scenarios coexist. Illustrative positions are marked DEMO.",
    empty: "No records stored. Import an official source or load the demonstration dataset.",
    unavailable: "Records could not be retrieved. Try refreshing when the data service is available.",
  };
  return <aside className={`data-note data-note-${mode}`} aria-label="Record origin"><span>{mode === "demo" ? "DEMO EDITION" : mode === "mixed" ? "MIXED EDITION" : "SOURCE NOTE"}</span><p>{messages[mode]}</p></aside>;
}
