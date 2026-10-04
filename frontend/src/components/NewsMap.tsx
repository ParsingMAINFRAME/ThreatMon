"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { CSSProperties, KeyboardEvent, PointerEvent } from "react";

import type { NewsEventView } from "@/lib/news-types";
import { clusterNewsEvents, coverageIntensity, COVERAGE_INTENSITY_BANDS } from "@/lib/news-view";
import { BASEMAP, LAND_PATHS, projectLocation, WORLD_HEIGHT, WORLD_WIDTH } from "@/lib/world-map";

type LocatedEvent = NewsEventView & { location: NonNullable<NewsEventView["location"]> };
type MapView = { zoom: 1 | 2 | 3; panX: number; panY: number; selectionId: string | null };
type MapDrag = {
  pointerId: number;
  startX: number;
  startY: number;
  panX: number;
  panY: number;
  width: number;
  height: number;
  target: HTMLDivElement;
};

const LONGITUDES = [-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150];
const LATITUDES = [-60, -30, 0, 30, 60];

function hasLocation(event: NewsEventView): event is LocatedEvent {
  const location = event.location;
  return event.scope === "located" && Boolean(location && Number.isFinite(location.lon) && Number.isFinite(location.lat)
    && location.lon >= -180 && location.lon <= 180 && location.lat >= -90 && location.lat <= 90);
}

function isIllustrative(event: LocatedEvent): boolean {
  return event.is_demo || event.location.precision === "illustrative";
}

function locationDescription(event: LocatedEvent): string {
  if (isIllustrative(event)) return "DEMO / illustrative location";
  if (event.grouping_status !== "source_event" && event.location.precision === "approximate_area") return "Place named in headline, not a verified site";
  return event.location.precision === "approximate_area" ? "Approximate area reference" : "Source-reported point";
}

function coordinates(event: LocatedEvent): string {
  const { lat, lon, precision } = event.location;
  const digits = precision === "source_point" ? 2 : 1;
  return `${Math.abs(lat).toFixed(digits)}° ${lat < 0 ? "S" : "N"} · ${Math.abs(lon).toFixed(digits)}° ${lon < 0 ? "W" : "E"}`;
}

type CoverageCounts = { story_count: number; official_report_count?: number };

function articleLabel(count: number): string {
  return `${count} collected ${count === 1 ? "article" : "articles"}`;
}

function reportLabel(count: number): string {
  return `${count} official ${count === 1 ? "report" : "reports"}`;
}

function officialReportCount(coverage: CoverageCounts): number {
  return coverage.official_report_count ?? 0;
}

function coverageLabel(coverage: CoverageCounts): string {
  const reports = officialReportCount(coverage);
  return [coverage.story_count > 0 ? articleLabel(coverage.story_count) : null, reports > 0 ? reportLabel(reports) : null]
    .filter(Boolean).join(" · ") || "0 articles";
}

function boundView(view: MapView): MapView {
  const limit = (view.zoom - 1) * 50;
  return { ...view, panX: Math.max(-limit, Math.min(limit, view.panX)), panY: Math.max(-limit, Math.min(limit, view.panY)) };
}

function centerLocation(view: MapView, location: { lon: number; lat: number }): MapView {
  const point = projectLocation(location.lon, location.lat);
  return boundView({ ...view, panX: (50 - point.x / WORLD_WIDTH * 100) * view.zoom, panY: (50 - point.y / WORLD_HEIGHT * 100) * view.zoom });
}

export function NewsMap({ events, selectedId, onSelect }: {
  events: NewsEventView[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const id = useId().replaceAll(":", "");
  const located = useMemo(() => events.filter(hasLocation), [events]);
  const selected = located.find((event) => event.id === selectedId);
  const [storedView, setView] = useState<MapView>({ zoom: 1, panX: 0, panY: 0, selectionId: selectedId });
  const [clusterId, setClusterId] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [viewportWidth, setViewportWidth] = useState(WORLD_WIDTH);
  const mapViewport = useRef<HTMLDivElement | null>(null);
  const drag = useRef<MapDrag | null>(null);
  const chooserHeading = useRef<HTMLHeadingElement | null>(null);
  const clusterTrigger = useRef<HTMLButtonElement | null>(null);
  const currentSelection = { ...storedView, selectionId: selectedId };
  const view = storedView.selectionId !== selectedId && selected && storedView.zoom > 1
    ? centerLocation(currentSelection, selected.location)
    : currentSelection;
  // Remember the current selection so returning to an earlier event cannot reuse an old pan.
  if (storedView.selectionId !== selectedId) setView(view);
  const zoom = storedView.zoom;
  const markers = useMemo(() => clusterNewsEvents(located, zoom, viewportWidth), [located, zoom, viewportWidth]);
  const activeCluster = markers.find((marker) => marker.kind === "cluster" && marker.id === clusterId);
  const activeClusterId = activeCluster?.id;
  const panLimit = (view.zoom - 1) * 50;
  const demoCount = located.filter(isIllustrative).length;
  const hasMappedEvents = located.length > 0;

  useEffect(() => {
    const element = mapViewport.current;
    if (!element || !hasMappedEvents) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0) setViewportWidth(Math.round(entry.contentRect.width));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [hasMappedEvents]);

  useEffect(() => {
    if (activeClusterId) chooserHeading.current?.focus({ preventScroll: false });
  }, [activeClusterId]);

  function stopDrag() {
    const active = drag.current;
    drag.current = null;
    if (active?.target.hasPointerCapture(active.pointerId)) active.target.releasePointerCapture(active.pointerId);
    setDragging(false);
  }

  function changeZoom(zoom: MapView["zoom"]) {
    stopDrag();
    setClusterId(null);
    const next = { ...view, zoom };
    setView(view.zoom === 1 && selected && zoom > 1
      ? centerLocation(next, selected.location)
      : boundView({ ...next, panX: view.panX * zoom / view.zoom, panY: view.panY * zoom / view.zoom }));
  }

  function panBy(x: number, y: number) {
    stopDrag();
    setView(boundView({ ...view, panX: view.panX + x, panY: view.panY + y }));
  }

  function startDrag(event: PointerEvent<HTMLDivElement>) {
    if (view.zoom === 1 || !event.isPrimary || event.button !== 0) return;
    if (event.target instanceof Element && event.target.closest("button, a")) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    drag.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, panX: view.panX, panY: view.panY, width: bounds.width, height: bounds.height, target: event.currentTarget };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
    setDragging(true);
  }

  function moveDrag(event: PointerEvent<HTMLDivElement>) {
    const active = drag.current;
    if (!active || active.pointerId !== event.pointerId) return;
    setView(boundView({ ...view, panX: active.panX + (event.clientX - active.startX) / active.width * 100, panY: active.panY + (event.clientY - active.startY) / active.height * 100 }));
    event.preventDefault();
  }

  function handleMapKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.target !== event.currentTarget) return;
    if (event.key === "+" || event.key === "=") {
      if (view.zoom < 3) changeZoom((view.zoom + 1) as MapView["zoom"]);
    } else if (event.key === "-") {
      if (view.zoom > 1) changeZoom((view.zoom - 1) as MapView["zoom"]);
    } else if (event.key === "Home") changeZoom(1);
    else if (view.zoom > 1 && event.key === "ArrowLeft") panBy(15, 0);
    else if (view.zoom > 1 && event.key === "ArrowRight") panBy(-15, 0);
    else if (view.zoom > 1 && event.key === "ArrowUp") panBy(0, 15);
    else if (view.zoom > 1 && event.key === "ArrowDown") panBy(0, -15);
    else return;
    event.preventDefault();
  }

  function selectEvent(event: LocatedEvent) {
    stopDrag();
    if (activeCluster && clusterTrigger.current?.isConnected) clusterTrigger.current.focus({ preventScroll: true });
    setClusterId(null);
    if (view.zoom > 1) setView(centerLocation({ ...view, selectionId: event.id }, event.location));
    onSelect(event.id);
  }

  function closeChooser() {
    setClusterId(null);
    if (clusterTrigger.current?.isConnected) clusterTrigger.current.focus({ preventScroll: true });
  }

  return <section className="news-map" aria-labelledby={`${id}-title`}>
    <header className="news-map-heading">
      <h2 id={`${id}-title`}>The world in view</h2>
      <div className="news-map-coverage">
        <span><strong>{located.length}</strong> mapped {located.length === 1 ? "event" : "events"}</span>
        <span><strong>{events.length - located.length}</strong> without a point</span>
      </div>
    </header>

    <div className="news-map-legend" aria-label="Coverage intensity legend">
      <span>Coverage intensity: {COVERAGE_INTENSITY_BANDS.map((band) => <span className="news-coverage-band" key={band.intensity}><i className={`coverage-${band.intensity}`} aria-hidden="true" /> {band.label}</span>)}</span>
      <span>Collected article volume, not severity or worldwide totals.</span>
    </div>

    {located.length ? <>
      <div className="news-map-toolbar" role="group" aria-label="Map view controls">
        <div className="news-map-zoom">
          <button type="button" onClick={() => changeZoom((view.zoom - 1) as MapView["zoom"])} disabled={view.zoom === 1} aria-label="Zoom out">−</button>
          <output aria-live="polite" aria-label="Map zoom">{view.zoom}×</output>
          <button type="button" onClick={() => changeZoom((view.zoom + 1) as MapView["zoom"])} disabled={view.zoom === 3} aria-label="Zoom in">+</button>
          <button type="button" onClick={() => changeZoom(1)} disabled={view.zoom === 1}>World view</button>
        </div>
        {view.zoom > 1 ? <div className="news-map-pan" role="group" aria-label="Pan map">
          <button type="button" onClick={() => panBy(15, 0)} disabled={view.panX >= panLimit} aria-label="Pan west">←</button>
          <button type="button" onClick={() => panBy(0, 15)} disabled={view.panY >= panLimit} aria-label="Pan north">↑</button>
          <button type="button" onClick={() => panBy(0, -15)} disabled={view.panY <= -panLimit} aria-label="Pan south">↓</button>
          <button type="button" onClick={() => panBy(-15, 0)} disabled={view.panX <= -panLimit} aria-label="Pan east">→</button>
          <span>Drag to pan</span>
        </div> : <span className="news-map-toolbar-note">Select a marker to explore the coverage.</span>}
      </div>

      <p id={`${id}-help`} className="sr-only">Event circles show collected article counts: green for 1 to 10, amber for 11 to 30, red for 31 or more. These counts describe collected coverage, not total worldwide coverage, severity or certainty. Neutral square markers show official report counts in the secondary bulletin view. Neutral groups labeled events represent nearby separate events. Select a group to choose an event. Use the zoom and pan controls, or focus the map and use plus, minus, Home, and arrow keys. The expandable located event index provides equivalent selection controls.</p>
      <div ref={mapViewport} className={`news-map-chart${view.zoom > 1 ? " is-zoomed" : ""}${dragging ? " is-dragging" : ""}`} tabIndex={0} role="group" aria-label="World news event map" aria-describedby={`${id}-help`} onKeyDown={handleMapKey} onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={stopDrag} onPointerCancel={stopDrag} onLostPointerCapture={stopDrag}>
        <div className="news-map-plane" style={{ transform: `translate(${view.panX}%, ${view.panY}%) scale(${view.zoom})` }}>
          <svg className="news-map-svg" viewBox={`0 0 ${WORLD_WIDTH} ${WORLD_HEIGHT}`} aria-hidden="true">
            <defs>
              <linearGradient id={`${id}-ocean`} x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#364144" />
                <stop offset="100%" stopColor="#20292d" />
              </linearGradient>
              <linearGradient id={`${id}-land`} x1="0" y1="0" x2="0.8" y2="1">
                <stop offset="0%" stopColor="#d0c7b5" />
                <stop offset="100%" stopColor="#9c927c" />
              </linearGradient>
            </defs>
            <rect width={WORLD_WIDTH} height={WORLD_HEIGHT} fill={`url(#${id}-ocean)`} />
            <g className="news-map-graticule">
              {LONGITUDES.map((lon) => <line key={lon} x1={projectLocation(lon, 0).x} y1="0" x2={projectLocation(lon, 0).x} y2={WORLD_HEIGHT} />)}
              {LATITUDES.map((lat) => <line key={lat} x1="0" y1={projectLocation(0, lat).y} x2={WORLD_WIDTH} y2={projectLocation(0, lat).y} />)}
            </g>
            <g className="news-map-land" fill={`url(#${id}-land)`}>
              {LAND_PATHS.map((path, index) => <path key={index} d={path} fillRule="evenodd" />)}
            </g>
          </svg>

          <div className="news-map-markers">
            {markers.map((marker) => {
              const point = projectLocation(marker.lon, marker.lat);
              const chosen = marker.events.some((event) => event.id === selectedId);
              const includesDemo = marker.events.some((event) => hasLocation(event) && isIllustrative(event));
              const onlyDemo = marker.events.every((event) => hasLocation(event) && isIllustrative(event));
              const screenX = 50 + view.panX + (point.x / WORLD_WIDTH * 100 - 50) * view.zoom;
              const screenY = 50 + view.panY + (point.y / WORLD_HEIGHT * 100 - 50) * view.zoom;
              const labelPosition = `${screenX > 65 ? " is-label-west" : screenX < 35 ? " is-label-east" : ""}${screenY > 60 ? " is-label-above" : ""}`;
              const style: CSSProperties = { left: `${point.x / WORLD_WIDTH * 100}%`, top: `${point.y / WORLD_HEIGHT * 100}%`, transform: `translate(-50%, -50%) scale(${1 / view.zoom})` };
              if (marker.kind === "cluster") return <button key={marker.id} type="button" className={`news-map-marker news-map-cluster${chosen ? " is-selected" : ""}${onlyDemo ? " is-demo" : ""}${labelPosition}`} style={{ ...style, transformOrigin: "0 0", transform: `scale(${1 / view.zoom}) translate(-${screenX > 90 ? 100 : screenX < 10 ? 0 : 50}%, -${screenY < 15 ? 0 : screenY > 85 ? 100 : 50}%)` }} aria-expanded={activeCluster?.id === marker.id} aria-controls={activeCluster?.id === marker.id ? `${id}-chooser` : undefined} aria-label={`${marker.events.length} separate nearby events, ${coverageLabel(marker)} in total. ${includesDemo ? "Includes DEMO events. " : ""}Open event chooser.`} title={`${marker.events.length} separate nearby events · ${coverageLabel(marker)}${includesDemo ? " · Includes DEMO events" : ""}`} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => {
                stopDrag();
                clusterTrigger.current = event.currentTarget;
                setClusterId(marker.id);
              }}>
                <strong>{marker.events.length}</strong><span>events</span>
                <span className="news-map-marker-caption" aria-hidden="true">{coverageLabel(marker)}{includesDemo ? <span className="news-map-marker-origin">DEMO{onlyDemo ? "" : " included"}</span> : null}</span>
              </button>;
              const event = marker.events[0];
              if (!event || !hasLocation(event)) return null;
              const candidate = event.grouping_status === "candidate";
              const reportCount = officialReportCount(event);
              const officialOnly = event.story_count === 0 && reportCount > 0;
              const mixedCoverage = event.story_count > 0 && reportCount > 0;
              const markerCount = officialOnly ? reportCount : event.story_count;
              const markerSize = Math.round(44 + Math.min(24, Math.sqrt(markerCount) * 3));
              return <button key={marker.id} type="button" className={`news-map-marker coverage-${coverageIntensity(event.story_count)}${officialOnly ? " is-official-report" : ""}${mixedCoverage ? " has-mixed-coverage" : ""}${chosen ? " is-selected" : ""}${isIllustrative(event) ? " is-demo" : ""}${labelPosition}`} style={{ ...style, "--news-marker-size": `${markerSize}px` } as CSSProperties} aria-pressed={chosen} aria-label={`${event.title}. ${coverageLabel(event)}.${candidate ? " Candidate association, unverified." : ""} ${locationDescription(event)}: ${event.location.label}. Select event.`} title={`${event.title} · ${coverageLabel(event)}${candidate ? " · Candidate association, unverified" : ""} · ${locationDescription(event)}`} onPointerDown={(event) => event.stopPropagation()} onClick={() => selectEvent(event)}>
                <span className="news-map-marker-count" aria-hidden="true">{markerCount}</span>
                <span className="news-map-marker-caption" aria-hidden="true">{officialOnly ? reportLabel(reportCount) : articleLabel(event.story_count)}{mixedCoverage ? <span className="news-map-caption-reports">+ {reportLabel(reportCount)}</span> : null}{candidate ? <span className="news-map-marker-origin">Candidate association</span> : null}{isIllustrative(event) ? <span className="news-map-marker-origin">DEMO</span> : event.location.precision === "approximate_area" ? <span className="news-map-marker-origin">Approximate area</span> : null}</span>
              </button>;
            })}
          </div>
        </div>
      </div>

      {activeCluster ? <section id={`${id}-chooser`} className="news-map-chooser" aria-labelledby={`${id}-chooser-title`} onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); closeChooser(); } }}>
        <div className="news-map-chooser-heading">
          <h3 id={`${id}-chooser-title`} ref={chooserHeading} tabIndex={-1}>{activeCluster.events.length} separate nearby events · {coverageLabel(activeCluster)}</h3>
          <button type="button" onClick={closeChooser}>Close chooser</button>
        </div>
        <p>These are separate events grouped for map readability. Their articles and official reports have not been combined into one incident.</p>
        <div className="news-map-chooser-list">
          {activeCluster.events.filter(hasLocation).map((event) => <button type="button" key={event.id} onClick={() => selectEvent(event)} aria-pressed={selectedId === event.id}>
            <strong>{event.title}</strong>
            <span>{coverageLabel(event)}{event.grouping_status === "candidate" ? " · Candidate association, unverified" : ""}</span>
            <span>{event.location.label} · {locationDescription(event)}</span>
          </button>)}
        </div>
      </section> : null}

      <div className="news-map-status" aria-live="polite" aria-atomic="true">
        {selected ? <>
          <strong>{selected.title}</strong>
          <span>{coverageLabel(selected)}{selected.grouping_status === "candidate" ? " · Candidate association, unverified" : ""}</span>
          <span>{selected.location.label} · {coordinates(selected)} · {locationDescription(selected)}</span>
          <span>Location confidence: {selected.location.confidence}. {selected.location.basis}</span>
        </> : <span>Select an event to view its articles and official reports. Locations are reference points, not impact areas.</span>}
      </div>
      <div className="news-map-legend" aria-label="Map legend">
        <span>Square number = official reports where no news articles are available.</span>
        <span>Mixed coverage keeps official report counts in a separate caption.</span>
        <span>“N events” = separate nearby events. Select the group to inspect each event and its coverage.</span>
        {demoCount ? <span>DEMO labels identify illustrative locations ({demoCount}).</span> : null}
        <span>Collected coverage may be capped or incomplete. Color is coverage intensity, not severity, certainty or total worldwide reporting.</span>
        <a href={BASEMAP.terms} target="_blank" rel="noreferrer">Natural Earth map data <span className="sr-only">(opens in a new tab)</span></a>
      </div>

      <details className="news-map-index">
        <summary>Located event index · {located.length}</summary>
        <div className="news-map-index-list" aria-label="Located events, including overlapping points">
          {located.map((event) => <button key={event.id} type="button" onClick={() => selectEvent(event)} aria-pressed={selectedId === event.id} className={selectedId === event.id ? "is-selected" : undefined}>
            <strong>{event.title}</strong>
            <span>{coverageLabel(event)}{event.grouping_status === "candidate" ? " · Candidate association, unverified" : ""}</span>
            <span>{event.location.label} · {locationDescription(event)}</span>
          </button>)}
        </div>
      </details>
    </> : <div className="news-map-empty">
      <strong>{events.length ? "No mapped locations in this view." : "No events match this view."}</strong>
      <p>{events.length ? `${events.length} ${events.length === 1 ? "event remains" : "events remain"} in the feed. Global coverage and events without a supported location are not assigned map points.` : "Change the topic, date window, or search to explore available coverage."}</p>
    </div>}
  </section>;
}
