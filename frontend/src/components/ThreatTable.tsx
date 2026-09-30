"use client";

import { useMemo, useRef, type RefObject } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Filters } from "./Filters";
import { ThreatMap } from "./ThreatMap";
import { categoryLabels, displayText, displayTitle, formatDate, formatDateTime, humanize } from "@/lib/presentation";
import type { ThreatCardData } from "@/lib/types";
import { evidenceHref, PAGE_SIZE, parseRegisterState, recordOrdinals, registerHref, registerPage, selectRegisterRecord, type RegisterState } from "@/lib/register-state";

function geographicScope(threat: ThreatCardData) {
  if (threat.map_location) return threat.map_location.label;
  if (threat.category === "space_planetary") return "Near-Earth scope · outside the terrestrial map";
  if (threat.geography.some((place) => place.toLowerCase() === "global")) return "Global scope · no geographic point";
  return `${threat.geography.join(" · ") || "Geography unspecified"} · no point location recorded`;
}

function RecordFocus({ threat, focusRef, state }: { threat: ThreatCardData | undefined; focusRef: RefObject<HTMLElement | null>; state: RegisterState }) {
  return <aside className="record-focus" ref={focusRef} tabIndex={-1} aria-label="Selected record summary" aria-live="polite">
    <div className="focus-heading"><span>SELECTED RECORD</span><span>{threat ? (threat.is_demo ? "DEMO SCENARIO" : "OFFICIAL SNAPSHOT") : "—"}</span></div>
    {threat ? <>
      <h2>{displayTitle(threat.title)}</h2>
      <p className="focus-summary">{displayText(threat.summary)}</p>
      <p className="focus-origin">{geographicScope(threat)}</p>
      <div className="focus-priority"><span>PRIORITY INDEX</span><strong>{threat.score.priority.toFixed(2)} <small>/ 100</small></strong></div>
      <dl className="focus-meta">
        <div><dt>Category</dt><dd>{categoryLabels[threat.category]}</dd></div>
        <div><dt>Event status</dt><dd>{humanize(threat.status)}</dd></div>
        <div><dt>Assessment confidence</dt><dd>{humanize(threat.score.confidence)}</dd></div>
        <div><dt>Source records</dt><dd>{threat.source_count ?? "Not recorded"}</dd></div>
        <div><dt>Record updated</dt><dd><time dateTime={threat.updated_at}>{formatDateTime(threat.updated_at)}</time></dd></div>
      </dl>
      <p className="focus-footnote">The brief records supporting claims, unknowns, and the assumptions behind this index.</p>
      <Link className="evidence-link" href={evidenceHref(threat.id, state)}>Read the evidence brief <span aria-hidden="true">↗</span></Link>
    </> : <><h2>No record in view.</h2><p className="focus-summary">Adjust the filters to inspect a stored event and its evidence.</p></>}
  </aside>;
}

export function ThreatTable({ threats }: { threats: ThreatCardData[] }) {
  const searchParams = useSearchParams();
  const state = parseRegisterState(searchParams);
  const { selectedCategory, selectedStatus, minSeverity, query, geography, mode, sort, selectedId, page } = state;
  const updateState = (next: RegisterState, replace = false) => {
    const href = registerHref(next);
    if (replace) window.history.replaceState(null, "", href);
    else window.history.pushState(null, "", href);
  };
  const worldDesk = useRef<HTMLDivElement>(null);
  const focusRef = useRef<HTMLElement>(null);
  const categories = useMemo(() => Array.from(new Set(threats.map((threat) => threat.category))).sort(), [threats]);
  const statuses = useMemo(() => Array.from(new Set(threats.map((threat) => threat.status))).sort(), [threats]);
  const active = selectedCategory !== "all" || selectedStatus !== "all" || minSeverity > 0 || Boolean(query.trim()) || Boolean(geography.trim()) || mode !== "all";
  const reset = () => updateState({ ...parseRegisterState(new URLSearchParams()), sort });
  const filteredThreats = threats.filter((threat) => {
    const searchable = `${threat.title} ${threat.summary} ${categoryLabels[threat.category]} ${threat.geography.join(" ")}`.toLowerCase();
    return (selectedCategory === "all" || threat.category === selectedCategory)
      && (selectedStatus === "all" || threat.status === selectedStatus)
      && threat.score.severity >= minSeverity
      && searchable.includes(query.trim().toLowerCase())
      && (!geography.trim() || threat.geography.some((place) => place.toLowerCase().includes(geography.trim().toLowerCase())))
      && (mode === "all" || (mode === "demo" ? threat.is_demo : !threat.is_demo));
  }).sort((a, b) => {
    if (sort === "title") return displayTitle(a.title).localeCompare(displayTitle(b.title)) || a.id.localeCompare(b.id);
    if (sort === "updated") return Date.parse(b.updated_at) - Date.parse(a.updated_at) || a.id.localeCompare(b.id);
    return b.score[sort] - a.score[sort] || a.id.localeCompare(b.id);
  });
  const selected = filteredThreats.find((threat) => threat.id === selectedId) ?? filteredThreats.find((threat) => threat.map_location && !threat.is_demo) ?? filteredThreats.find((threat) => threat.map_location) ?? filteredThreats[0];
  const pageCount = Math.max(1, Math.ceil(filteredThreats.length / PAGE_SIZE));
  const currentPage = registerPage(page, filteredThreats.length);
  const firstIndex = (currentPage - 1) * PAGE_SIZE;
  const visibleThreats = filteredThreats.slice(firstIndex, firstIndex + PAGE_SIZE);
  const filterChange = <K extends keyof RegisterState,>(key: K) => (value: RegisterState[K]) =>
    updateState({ ...state, [key]: value, page: 1, selectedId: null }, key === "query" || key === "geography" || key === "minSeverity");
  const ordinals = recordOrdinals(filteredThreats);
  const selectRecord = (id: string) => updateState(selectRegisterRecord(state, id, filteredThreats));
  const selectFromRegister = (id: string) => {
    selectRecord(id);
    requestAnimationFrame(() => {
      focusRef.current?.focus({ preventScroll: true });
      const target = window.matchMedia("(max-width: 850px)").matches ? focusRef.current : worldDesk.current;
      target?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
    });
  };
  const locatedCount = filteredThreats.filter((threat) => threat.map_location).length;

  return <>
    <Filters categories={categories} statuses={statuses} selectedCategory={selectedCategory} selectedStatus={selectedStatus} minSeverity={minSeverity} query={query} geography={geography} mode={mode} sort={sort} active={active} onCategoryChange={filterChange("selectedCategory")} onStatusChange={filterChange("selectedStatus")} onMinSeverityChange={filterChange("minSeverity")} onQueryChange={filterChange("query")} onGeographyChange={filterChange("geography")} onModeChange={filterChange("mode")} onSortChange={filterChange("sort")} onReset={reset} />
    <div className="world-desk" ref={worldDesk}>
      <div className="atlas-column"><ThreatMap threats={filteredThreats} selectedId={selected?.id ?? null} onSelect={selectRecord} ordinals={ordinals} /></div>
      <RecordFocus threat={selected} focusRef={focusRef} state={{ ...state, page: currentPage }} />
    </div>
    <section className="register-section" id="event-register" tabIndex={-1} aria-labelledby="register-title">
      <header className="register-heading"><div><p className="section-kicker">02 / STORED OBSERVATIONS</p><h2 id="register-title">Event register</h2></div><p role="status">{filteredThreats.length.toLocaleString()} of {threats.length.toLocaleString()} records · {locatedCount} with points</p></header>
      {filteredThreats.length ? <>
        <div className="register-columns" aria-hidden="true"><span>No.</span><span>Event / scope</span><span>Status / assessment</span><span style={{textAlign:"right"}}>Priority</span><span style={{textAlign:"right"}}>Inspect</span></div>
        <div aria-label="Threat event records">{visibleThreats.map((threat) => <article key={threat.id} data-record-id={threat.id} className={`event-row${selected?.id === threat.id ? " is-selected" : ""}`}>
          <span className="event-number" aria-hidden="true">{String(ordinals.get(threat.id)).padStart(2, "0")}</span>
          <div className="event-content"><div className="event-classification"><span>{categoryLabels[threat.category]}</span><span className="event-origin">{threat.is_demo ? "Demo scenario" : "Official snapshot"}</span>{threat.source_count !== undefined ? <span>{threat.source_count} source {threat.source_count === 1 ? "record" : "records"}</span> : null}</div><Link href={evidenceHref(threat.id, { ...state, page: currentPage })} className="event-title">{displayTitle(threat.title)}</Link><p className="event-geography">{threat.geography.join(" · ") || "Geography unspecified"}{threat.map_location ? " · point available" : ""}</p></div>
          <div className="event-status"><span>{humanize(threat.status)}</span><span>{humanize(threat.score.confidence)} confidence</span></div>
          <div className="event-priority" aria-label={`Priority index ${threat.score.priority.toFixed(2)} of 100`}>{threat.score.priority.toFixed(2)}<small>Severity {threat.score.severity.toFixed(0)}</small></div>
          <div className="event-action"><button type="button" className="locate-button" aria-pressed={selected?.id === threat.id} aria-label={`Inspect ${displayTitle(threat.title)} in the ${threat.map_location ? "map" : "summary"}`} onClick={() => selectFromRegister(threat.id)}>{threat.map_location ? "Locate ↗" : "Summary ↗"}</button><time dateTime={threat.updated_at} title={formatDateTime(threat.updated_at)}>{formatDate(threat.updated_at)}</time></div>
        </article>)}</div>
        <nav className="register-pagination" aria-label="Event register pages"><span>{firstIndex + 1}–{Math.min(firstIndex + PAGE_SIZE, filteredThreats.length)} of {filteredThreats.length.toLocaleString()} records</span><div className="pagination-buttons"><button type="button" disabled={currentPage === 1} onClick={() => updateState({ ...state, page: currentPage - 1 })}>← Previous</button><span>{currentPage} / {pageCount}</span><button type="button" disabled={currentPage === pageCount} onClick={() => updateState({ ...state, page: currentPage + 1 })}>Next →</button></div></nav>
      </> : <div className="register-empty"><h3>{threats.length ? "No records match this view." : "The register is empty."}</h3><p>{threats.length ? "Try another subject, location, or severity threshold." : "Load the demo scenarios or ingest an official source to begin."}</p>{active ? <button type="button" className="text-control" onClick={reset}>Clear filters</button> : null}</div>}
    </section>
  </>;
}
