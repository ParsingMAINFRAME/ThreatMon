"use client";

import { useId, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

import { displayTitle } from "@/lib/presentation";
import type { MapLocation, ThreatCardData } from "@/lib/types";
import { BASEMAP, LAND_PATHS, projectLocation, WORLD_HEIGHT, WORLD_WIDTH } from "@/lib/world-map";
import "@/app/map.css";

type MappableThreat = ThreatCardData & { map_location?: MapLocation | null };
type LocatedThreat = MappableThreat & { map_location: MapLocation };

function hasLocation(threat: MappableThreat): threat is LocatedThreat {
  const point = threat.map_location;
  return Boolean(point && Number.isFinite(point.lon) && Number.isFinite(point.lat)
    && point.lon >= -180 && point.lon <= 180 && point.lat >= -90 && point.lat <= 90);
}

function coordinates(point: MapLocation): string {
  return `${Math.abs(point.lat).toFixed(2)}° ${point.lat < 0 ? "S" : "N"} · ${Math.abs(point.lon).toFixed(2)}° ${point.lon < 0 ? "W" : "E"}`;
}

function isIllustrative(threat: LocatedThreat): boolean {
  return threat.is_demo || threat.map_location.origin === "synthetic_demo" || threat.map_location.precision === "illustrative";
}

const LONGITUDES = [-150, -120, -90, -60, -30, 0, 30, 60, 90, 120, 150];
const LATITUDES = [-60, -30, 0, 30, 60];

type MapView = { zoom: 1 | 2 | 3; panX: number; panY: number; selectionId: string | null };
type MapDrag = { pointerId: number; startX: number; startY: number; panX: number; panY: number; width: number; height: number; target: HTMLDivElement };

function boundView(view: MapView): MapView {
  const limit = (view.zoom - 1) * 50;
  return { ...view, panX: Math.max(-limit, Math.min(limit, view.panX)), panY: Math.max(-limit, Math.min(limit, view.panY)) };
}

function centerPoint(view: MapView, point: { x: number; y: number }): MapView {
  return boundView({ ...view, panX: (50 - point.x / WORLD_WIDTH * 100) * view.zoom, panY: (50 - point.y / WORLD_HEIGHT * 100) * view.zoom });
}

export function ThreatMap({
  threats,
  selectedId,
  onSelect,
  ordinals,
}: {
  threats: MappableThreat[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  ordinals: ReadonlyMap<string, number>;
}) {
  const id = useId().replaceAll(":", "");
  const located = threats.filter(hasLocation);
  const selected = located.find((threat) => threat.id === selectedId);
  const selectedPoint = selected ? projectLocation(selected.map_location.lon, selected.map_location.lat) : null;
  const demoCount = located.filter(isIllustrative).length;
  const [storedView, setView] = useState<MapView>({ zoom: 1, panX: 0, panY: 0, selectionId: selectedId });
  const [dragging, setDragging] = useState(false);
  const drag = useRef<MapDrag | null>(null);
  // Retain each external selection's displayed viewport. Otherwise an A → B → A
  // selection can resurrect A's old pan and leave its marker offscreen.
  const currentSelection = { ...storedView, selectionId: selectedId };
  const view = storedView.selectionId !== selectedId && selectedPoint && storedView.zoom > 1
    ? centerPoint(currentSelection, selectedPoint)
    : currentSelection;
  if (storedView.selectionId !== selectedId) setView(view);
  const panLimit = (view.zoom - 1) * 50;

  function stopDrag() {
    const active = drag.current;
    drag.current = null;
    if (active?.target.hasPointerCapture(active.pointerId)) active.target.releasePointerCapture(active.pointerId);
    setDragging(false);
  }

  function changeZoom(zoom: MapView["zoom"]) {
    stopDrag();
    const next = { ...view, zoom };
    setView(view.zoom === 1 && selectedPoint && zoom > 1
      ? centerPoint(next, selectedPoint)
      : boundView({ ...next, panX: view.panX * zoom / view.zoom, panY: view.panY * zoom / view.zoom }));
  }

  function panBy(x: number, y: number) {
    stopDrag();
    setView(boundView({ ...view, panX: view.panX + x, panY: view.panY + y }));
  }

  function startDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (view.zoom === 1 || !event.isPrimary || event.button !== 0) return;
    if (event.target instanceof Element && event.target.closest("button, a")) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    drag.current = { pointerId: event.pointerId, startX: event.clientX, startY: event.clientY, panX: view.panX, panY: view.panY, width: bounds.width, height: bounds.height, target: event.currentTarget };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
    setDragging(true);
  }

  function moveDrag(event: ReactPointerEvent<HTMLDivElement>) {
    const active = drag.current;
    if (!active || active.pointerId !== event.pointerId) return;
    setView(boundView({ ...view, panX: active.panX + (event.clientX - active.startX) / active.width * 100, panY: active.panY + (event.clientY - active.startY) / active.height * 100 }));
    event.preventDefault();
  }

  function selectLocation(threat: LocatedThreat) {
    stopDrag();
    if (view.zoom > 1) setView(centerPoint({ ...view, selectionId: threat.id }, projectLocation(threat.map_location.lon, threat.map_location.lat)));
    onSelect(threat.id);
  }

  return (
    <section className="atlas" aria-labelledby={`${id}-title`}>
      <header className="atlas-heading">
        <div className="atlas-heading-title">
          <h2 id={`${id}-title`}>Geographic coverage</h2>
        </div>
        <div className="atlas-coverage" aria-label={`${located.length} located records, ${threats.length - located.length} without a point location`}>
          <span><strong>{String(located.length).padStart(2, "0")}</strong> located</span>
          <span><strong>{String(threats.length - located.length).padStart(2, "0")}</strong> without a point</span>
        </div>
      </header>

      <div className="atlas-frame">
        <div className={`atlas-chart${view.zoom > 1 ? " is-zoomed" : ""}${dragging ? " is-dragging" : ""}`} role="group" aria-label="World map. Select a numbered location to inspect its record." aria-describedby={`${id}-help`} onPointerDown={startDrag} onPointerMove={moveDrag} onPointerUp={stopDrag} onPointerCancel={stopDrag} onLostPointerCapture={stopDrag}>
          <p id={`${id}-help`} className="sr-only">Use the zoom buttons to magnify the map. When zoomed, drag the map or use the directional pan buttons. Reset view returns to the whole world. The located record index below the map also selects and centers points.</p>
          <div className="atlas-transform-plane" style={{ transform: `translate(${view.panX}%, ${view.panY}%) scale(${view.zoom})` }}>
          <svg className="atlas-svg" viewBox={`0 0 ${WORLD_WIDTH} ${WORLD_HEIGHT}`} aria-hidden="true">
            <defs>
              <linearGradient id={`${id}-ocean`} x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#303839" />
                <stop offset="55%" stopColor="#252e30" />
                <stop offset="100%" stopColor="#1b2325" />
              </linearGradient>
              <linearGradient id={`${id}-land`} x1="0" y1="0" x2="0.8" y2="1">
                <stop offset="0%" stopColor="#c9c7b7" />
                <stop offset="100%" stopColor="#938f7d" />
              </linearGradient>
              <pattern id={`${id}-dots`} width="8" height="8" patternUnits="userSpaceOnUse">
                <circle cx="4" cy="4" r="0.55" fill="#ece3cc" opacity="0.11" />
              </pattern>
              <clipPath id={`${id}-land-clip`}>
                {LAND_PATHS.map((path, index) => <path key={index} d={path} fillRule="evenodd" />)}
              </clipPath>
            </defs>

            <rect width={WORLD_WIDTH} height={WORLD_HEIGHT} fill={`url(#${id}-ocean)`} />
            <g className="atlas-graticule">
              {LONGITUDES.map((lon) => <line key={lon} x1={projectLocation(lon, 0).x} y1="0" x2={projectLocation(lon, 0).x} y2={WORLD_HEIGHT} />)}
              {LATITUDES.map((lat) => <line key={lat} x1="0" y1={projectLocation(0, lat).y} x2={WORLD_WIDTH} y2={projectLocation(0, lat).y} className={lat === 0 ? "atlas-equator" : undefined} />)}
            </g>

            <g className="atlas-land" fill={`url(#${id}-land)`}>
              {LAND_PATHS.map((path, index) => <path key={index} d={path} fillRule="evenodd" />)}
            </g>
            <rect width={WORLD_WIDTH} height={WORLD_HEIGHT} fill={`url(#${id}-dots)`} clipPath={`url(#${id}-land-clip)`} />

            <g className="atlas-ocean-labels">
              <text x="170" y="280">PACIFIC</text>
              <text x="420" y="276">ATLANTIC</text>
              <text x="725" y="335">INDIAN</text>
              <text x="946" y="280" textAnchor="end">PACIFIC</text>
            </g>

            <g className="atlas-axis-labels">
              {[-120, -60, 0, 60, 120].map((lon) => <text key={lon} x={projectLocation(lon, 0).x + 5} y="18">{Math.abs(lon)}°{lon === 0 ? "" : lon < 0 ? "W" : "E"}</text>)}
              {[60, 30, 0, -30, -60].map((lat) => <text key={lat} x="11" y={projectLocation(0, lat).y - 5}>{Math.abs(lat)}°{lat === 0 ? "" : lat < 0 ? "S" : "N"}</text>)}
            </g>

            {selectedPoint ? <g className="atlas-selected-guides">
              <line x1={selectedPoint.x} y1="28" x2={selectedPoint.x} y2={WORLD_HEIGHT - 15} />
              <line x1="30" y1={selectedPoint.y} x2={WORLD_WIDTH - 18} y2={selectedPoint.y} />
              <circle cx={selectedPoint.x} cy={selectedPoint.y} r="23" />
              <path d={`M${selectedPoint.x - 31},${selectedPoint.y - 10}v-12h12 M${selectedPoint.x + 31},${selectedPoint.y - 10}v-12h-12 M${selectedPoint.x - 31},${selectedPoint.y + 10}v12h12 M${selectedPoint.x + 31},${selectedPoint.y + 10}v12h-12`} />
            </g> : null}
          </svg>

          <div className="atlas-markers">
            {located.map((threat) => {
              const point = projectLocation(threat.map_location.lon, threat.map_location.lat);
              const visibleX = (point.x / WORLD_WIDTH * 100 - 50) * view.zoom + 50 + view.panX;
              const edge = visibleX > 88 ? " is-east-edge" : visibleX < 12 ? " is-west-edge" : "";
              const illustrative = isIllustrative(threat);
              const isSelected = selectedId === threat.id;
              return (
                <button
                  type="button"
                  key={threat.id}
                  className={`atlas-marker${isSelected ? " is-selected" : ""}${illustrative ? " is-illustrative" : ""}${threat.score.severity >= 70 ? " is-high-severity" : ""}${edge}`}
                  style={{ left: `${point.x / WORLD_WIDTH * 100}%`, top: `${point.y / WORLD_HEIGHT * 100}%`, transform: `translate(-50%, -50%) scale(${1 / view.zoom})` }}
                  onPointerDown={(event) => event.stopPropagation()}
                  onClick={() => selectLocation(threat)}
                  aria-pressed={isSelected}
                  aria-label={`Record ${ordinals.get(threat.id)}. ${displayTitle(threat.title)}. ${illustrative ? "DEMO, illustrative location" : "Source-reported location"}: ${threat.map_location.label}. Select record.`}
                  title={`${displayTitle(threat.title)} · ${illustrative ? "DEMO / illustrative" : "source-reported"}`}
                >
                  <span className="atlas-marker-dot" aria-hidden="true" />
                  <span className="atlas-marker-number" aria-hidden="true">{String(ordinals.get(threat.id)).padStart(2, "0")}</span>
                  <span className="atlas-marker-tooltip" aria-hidden="true">
                    <span>{illustrative ? "DEMO / ILLUSTRATIVE" : "SOURCE-REPORTED POINT"}</span>
                    <strong>{displayTitle(threat.title)}</strong>
                  </span>
                </button>
              );
            })}
          </div>
          </div>

          <div className="atlas-view-controls" role="group" aria-label="Map view controls">
            <div className="atlas-zoom-controls">
              <button type="button" onClick={() => changeZoom((view.zoom - 1) as MapView["zoom"])} disabled={view.zoom === 1} aria-label="Zoom out">−</button>
              <output aria-live="polite" aria-label="Map zoom">{view.zoom}×</output>
              <button type="button" onClick={() => changeZoom((view.zoom + 1) as MapView["zoom"])} disabled={view.zoom === 3} aria-label="Zoom in">+</button>
              <button type="button" className="atlas-reset-view" onClick={() => changeZoom(1)} disabled={view.zoom === 1}>Reset view</button>
            </div>
            {view.zoom > 1 ? <div className="atlas-pan-controls" role="group" aria-label="Pan map">
              <button type="button" onClick={() => panBy(15, 0)} disabled={view.panX >= panLimit} aria-label="Pan west">←</button>
              <button type="button" onClick={() => panBy(0, 15)} disabled={view.panY >= panLimit} aria-label="Pan north">↑</button>
              <button type="button" onClick={() => panBy(0, -15)} disabled={view.panY <= -panLimit} aria-label="Pan south">↓</button>
              <button type="button" onClick={() => panBy(-15, 0)} disabled={view.panX <= -panLimit} aria-label="Pan east">→</button>
              <span>Drag to pan</span>
            </div> : null}
          </div>

          <div className="atlas-map-note" aria-hidden="true">EQUIRECTANGULAR / WGS84</div>
          <div className="atlas-north" aria-hidden="true"><span>N</span><svg viewBox="0 0 24 38"><path d="M12 2 22 30 12 24 2 30Z" fill="none" stroke="currentColor" strokeWidth="1" /><path d="M12 2V24L2 30Z" fill="currentColor" opacity=".55" /></svg></div>

          {!located.length ? <div className="atlas-empty"><strong>No point locations in this view.</strong><span>Global or unlocated records remain in the event register.</span></div> : null}
        </div>

        <div className="atlas-map-status" aria-live="polite">
          <span className="atlas-status-dot" aria-hidden="true" />
          {selected ? <>
            <strong>{selected.map_location.label}</strong>
            <span className="atlas-status-coordinate">{coordinates(selected.map_location)}</span>
            <span className="atlas-status-mode">{isIllustrative(selected) ? "ILLUSTRATIVE DEMO POINT" : "SOURCE-REPORTED POINT"}</span>
          </> : <>
            <strong>Select a location to inspect its evidence.</strong>
            <span className="atlas-status-mode">POINTS LOCATE RECORDS, NOT IMPACT AREAS</span>
          </>}
        </div>
      </div>

      <div className="atlas-footer">
        <div className="atlas-legend" aria-label="Map marker legend">
          <span><i className="atlas-legend-point" /> Reported point</span>
          <span><i className="atlas-legend-demo" /> Illustrative demo{demoCount ? ` (${demoCount})` : ""}</span>
          <span><i className="atlas-legend-severity" /> Severity input ≥70</span>
        </div>
        <a href={BASEMAP.terms} target="_blank" rel="noreferrer">Made with Natural Earth <span aria-hidden="true">↗</span></a>
      </div>

      {located.length ? <details className="atlas-index-disclosure"><summary>Located record index · {located.length}<span aria-hidden="true" /></summary><div className="atlas-location-index" aria-label="Located records. Alternative controls for overlapping points.">
        {located.map((threat) => <button key={threat.id} type="button" onClick={() => selectLocation(threat)} aria-pressed={selectedId === threat.id} className={selectedId === threat.id ? "is-selected" : undefined}>
          <span>{String(ordinals.get(threat.id)).padStart(2, "0")}</span>
          {displayTitle(threat.title)}
          {isIllustrative(threat) ? <small>DEMO</small> : null}
        </button>)}
      </div></details> : null}
    </section>
  );
}
