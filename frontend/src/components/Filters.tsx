"use client";

import { useEffect, useRef } from "react";
import { categoryLabels, humanize } from "@/lib/presentation";
import type { ThreatCategory, ThreatStatus } from "@/lib/types";

export type SortOption = "priority" | "severity" | "updated" | "title";

type FiltersProps = {
  categories: ThreatCategory[]; statuses: ThreatStatus[]; selectedCategory: string; selectedStatus: string;
  minSeverity: number; query: string; geography: string; mode: string; sort: SortOption; active: boolean;
  onCategoryChange: (value: string) => void; onStatusChange: (value: string) => void;
  onMinSeverityChange: (value: number) => void; onQueryChange: (value: string) => void;
  onGeographyChange: (value: string) => void; onModeChange: (value: string) => void;
  onSortChange: (value: SortOption) => void; onReset: () => void;
};

export function Filters(props: FiltersProps) {
  const moreFilters = useRef<HTMLDetailsElement>(null);
  const hasAdditionalFilters = Boolean(props.geography.trim()) || props.minSeverity > 0;
  useEffect(() => {
    if (hasAdditionalFilters && moreFilters.current) moreFilters.current.open = true;
  }, [hasAdditionalFilters]);

  return (
    <div className="filter-desk">
      <div className="filter-primary">
        <label className="desk-field search-field"><span>Search the register</span><input type="search" value={props.query} onChange={(event) => props.onQueryChange(event.target.value)} placeholder="Title, subject, or place…" /></label>
        <label className="desk-field"><span>Category</span><select value={props.selectedCategory} onChange={(event) => props.onCategoryChange(event.target.value)}><option value="all">All categories</option>{props.categories.map((value) => <option key={value} value={value}>{categoryLabels[value]}</option>)}</select></label>
        <label className="desk-field"><span>Event status</span><select value={props.selectedStatus} onChange={(event) => props.onStatusChange(event.target.value)}><option value="all">All statuses</option>{props.statuses.map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
        <label className="desk-field"><span>Record origin</span><select value={props.mode} onChange={(event) => props.onModeChange(event.target.value)}><option value="all">All records</option><option value="demo">Demo scenarios</option><option value="live">Official snapshots</option></select></label>
        <label className="desk-field sort-field"><span>Order by</span><select value={props.sort} onChange={(event) => props.onSortChange(event.target.value as SortOption)}><option value="priority">Priority index</option><option value="severity">Severity input</option><option value="updated">Latest update</option><option value="title">Title A–Z</option></select></label>
        <details className="desk-more" ref={moreFilters}><summary>More filters</summary><div className="filter-secondary">
          <label className="desk-field"><span>Geography contains</span><input value={props.geography} onChange={(event) => props.onGeographyChange(event.target.value)} placeholder="Any location" /></label>
          <label className="desk-field"><span>Minimum severity / 100</span><input type="number" min="0" max="100" step="5" value={props.minSeverity} onChange={(event) => props.onMinSeverityChange(Math.min(100, Math.max(0, Number(event.target.value) || 0)))} /></label>
        </div></details>
      </div>
      {props.active ? <div className="filter-active"><span>Filtered view · map and register update together</span><button onClick={props.onReset} type="button" className="text-control">Clear filters</button></div> : null}
    </div>
  );
}
