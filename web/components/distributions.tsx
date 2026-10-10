"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { gsap } from "gsap";
import { useMotion } from "../lib/motion";
import "./evidence.css";

type Stats = { min: number; q1: number; median: number; q3: number; max: number };
type Source = {
  events: number; uncensored_decades: Record<string, number>; dilution_values: Record<string, number>;
  altitude_bands: Record<string, number>; covariance_trace_decades: Record<string, number>;
  miss_distance_km: Stats; relative_speed_kms: Stats; mahalanobis_distance: Stats;
  pc_by_dilution?: { robust?: { above_action_threshold: number }; diluted?: { above_action_threshold: number } };
};
type Summary = { population: { events: number; censored: number; pc_null: number; above_action_threshold: number; by_source: Record<string, Source> } };
type Event = { event_id: string; pc: number | null; pc_is_floored: boolean; miss_distance_km: number; dilution: number | null; stratum: string };
type Bar = { label: string; value: number; color?: string; emphasis?: boolean; fullLabel?: string };
type Legend = { label: string; color: string };
type Chart = { title: string; note: string; scope: "population" | "sample"; bars?: Bar[]; log?: boolean; unit?: string; legend?: Legend[]; scatter?: boolean };

const colors = { olive: "#777b45", rust: "#b45436", acid: "#d0d68b", censored: "#969080", unavailable: "#29261f", grid: "#d6d1c4" };
const count = (value: number) => value.toLocaleString("en-US");
const exact = (value: number) => Number.isInteger(value) ? count(value) : String(value);
const short = (value: number) => {
  const size = Math.abs(value);
  if (!size) return "0";
  if (size >= 1e6) return `${(value / 1e6).toFixed(1)}m`;
  if (size >= 1e3) return `${Number((value / 1e3).toFixed(1))}k`;
  if (size < .01) return value.toExponential(1);
  return String(Number(value.toFixed(size < 1 ? 3 : 2)));
};
const sourceName = (name: string) => name === "spherical" ? "Sph." : name.toUpperCase();

function useChartEntrance(ref: React.RefObject<HTMLElement | null>) {
  const { enabled } = useMotion();
  useEffect(() => {
    const element = ref.current;
    if (!element || !enabled) return;
    const context = gsap.context(() => {}, element);
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      context.add(() => {
        gsap.from(element, { y: 24, autoAlpha: 0, duration: .7, ease: "power3.out" });
        gsap.from(element.querySelectorAll(".atlas-bar"), { scaleY: 0, transformOrigin: "center bottom", duration: .9, stagger: .025, ease: "power3.out", delay: .1 });
      });
      observer.disconnect();
    }, { threshold: .12 });
    observer.observe(element);
    return () => { observer.disconnect(); context.revert(); };
  }, [ref, enabled]);
}

function LegendRow({ items }: { items: Legend[] }) {
  return <div className="atlas-legend">{items.map((item) => <span key={item.label}><i style={{ background: item.color }} aria-hidden="true" />{item.label}</span>)}</div>;
}

function BarPlot({ bars, title, logarithmic, unit = "records" }: { bars: Bar[]; title: string; logarithmic?: boolean; unit?: string }) {
  const id = useId();
  const [readout, setReadout] = useState("Hover or focus a bar to read the exact value.");
  const width = 520, height = 275;
  const left = 53, right = 14, top = 31, bottom = 79;
  const plotWidth = width - left - right, plotHeight = height - top - bottom;
  const maximum = Math.max(...bars.map((bar) => bar.value), 1);
  const useLog = logarithmic ?? maximum > 500;
  const scale = (value: number) => useLog ? Math.log10(1 + Math.max(0, value)) / Math.log10(1 + maximum) * plotHeight : value / maximum * plotHeight;
  const candidates = useLog ? [0, ...Array.from({ length: Math.ceil(Math.log10(maximum + 1)) + 1 }, (_, i) => 10 ** i).filter((value) => value <= maximum)] : [0, maximum / 2, maximum];
  const ticks = candidates.filter((value, index) => index === 0 || scale(value) - scale(candidates[index - 1]) > 13);
  const slot = plotWidth / bars.length, barWidth = Math.max(3, Math.min(slot - 6, 35));
  return <>
    <svg className="atlas-svg" viewBox={`0 0 ${width} ${height}`} role="group" aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`}>
      <title id={`${id}-title`}>{title}</title><desc id={`${id}-description`}>Bar chart in {unit}. {useLog ? "Height is log base ten of one plus the value; tick labels are in original units." : "Linear scale starting at zero."} Focus a bar to inspect its value, or expand the exact-value table below.</desc>
      <text x={left} y={12} className="atlas-axis-note">{unit}</text><text x={width - right} y={12} textAnchor="end" className="atlas-axis-note">{useLog ? "log₁₀(1 + value) height" : "linear scale"}</text>
      {ticks.map((tick) => { const y = top + plotHeight - scale(tick); return <g key={tick} aria-hidden="true"><line x1={left} x2={width - right} y1={y} y2={y} stroke={colors.grid} /><text x={left - 8} y={y + 4} textAnchor="end" className="atlas-tick">{short(tick)}</text></g>; })}
      {bars.map((bar, index) => {
        const barHeight = scale(bar.value), x = left + index * slot + (slot - barWidth) / 2, y = top + plotHeight - barHeight;
        const label = `${bar.fullLabel ?? bar.label}: ${exact(bar.value)} ${unit}`;
        return <g key={`${bar.label}-${index}`}><rect className="atlas-bar" x={x} y={bar.value === 0 ? y - 2 : y} width={barWidth} height={Math.max(barHeight, 2)} fill={bar.color ?? colors.olive} fillOpacity={bar.value === 0 ? .15 : 1} stroke={bar.emphasis ? colors.unavailable : "none"} strokeWidth={bar.emphasis ? 1.5 : 0} tabIndex={0} role="img" aria-label={label} onFocus={() => setReadout(label)} onMouseEnter={() => setReadout(label)}><title>{label}</title></rect>{bars.length <= 12 && <text x={x + barWidth / 2} y={y - 7} textAnchor="middle" className="atlas-value" aria-hidden="true">{short(bar.value)}</text>}<text x={x + barWidth / 2} y={top + plotHeight + 14} textAnchor="end" transform={`rotate(-42 ${x + barWidth / 2} ${top + plotHeight + 14})`} className="atlas-category" aria-hidden="true">{bar.label}</text></g>;
      })}
    </svg>
    <p className="atlas-readout" role="status" aria-live="polite">{readout}</p>
    <details className="atlas-values"><summary>Read exact values <span aria-hidden="true">+</span></summary><div className="atlas-table-scroll"><table><caption>{title} · {unit}</caption><thead><tr><th scope="col">Category</th><th scope="col">{unit}</th></tr></thead><tbody>{bars.map((bar, index) => <tr key={`${bar.label}-${index}`}><th scope="row">{bar.fullLabel ?? bar.label}</th><td>{exact(bar.value)}</td></tr>)}</tbody></table></div></details>
  </>;
}

function ScatterPlot({ events }: { events: Event[] }) {
  const id = useId();
  const [active, setActive] = useState(0);
  const [page, setPage] = useState(0);
  const plotted = useMemo(() => events.filter((event) => event.pc != null), [events]);
  const selected = plotted[active];
  const width = 520, height = 322, left = 57, right = 15, top = 35, bottom = 49;
  const w = width - left - right, h = height - top - bottom;
  const sx = (value: number) => left + (Math.log10(Math.max(value, .005)) - Math.log10(.005)) / (Math.log10(70) - Math.log10(.005)) * w;
  const sy = (logValue: number) => top + h - ((logValue + 10.5) / 7.5) * h;
  const pointY = (event: Event, index: number) => event.pc_is_floored ? sy(-10.35) + ((index * 37 % 101) / 100 - .5) * 8 : sy(Math.log10(event.pc!));
  const description = (event: Event) => `${event.event_id} · miss ${exact(event.miss_distance_km)} km · ${event.pc_is_floored ? "Pc ≤ 1e−10 (censored bound)" : `Pc ${event.pc?.toExponential(5)}`} · dilution ${event.dilution == null ? "unknown" : event.dilution ? "flagged" : "unflagged"}`;
  const pageSize = 20, pageCount = Math.ceil(events.length / pageSize);
  return <>
    <svg className="atlas-svg atlas-scatter" viewBox={`0 0 ${width} ${height}`} tabIndex={0} role="group" aria-labelledby={`${id}-title`} aria-describedby={`${id}-description`} onKeyDown={(event) => {
      if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key) || !plotted.length) return;
      event.preventDefault();
      setActive((index) => event.key === "Home" ? 0 : event.key === "End" ? plotted.length - 1 : (index + (["ArrowLeft", "ArrowDown"].includes(event.key) ? -1 : 1) + plotted.length) % plotted.length);
    }}>
      <title id={`${id}-title`}>Miss distance and collision probability</title><desc id={`${id}-description`}>Logarithmic axes. Censored bounds occupy a separate band; band height is not a probability. Use arrow keys to inspect individual events; Home and End select the first and last. Exact values, including missing probabilities, appear below.</desc>
      <text x={left} y={14} className="atlas-axis-note">Calculated probability · P<tspan baselineShift="sub">c</tspan></text>
      {Array.from({ length: 8 }, (_, index) => index - 10).map((value) => <g key={value} aria-hidden="true"><line x1={left} x2={width - right} y1={sy(value)} y2={sy(value)} stroke={colors.grid} /><text x={left - 9} y={sy(value) + 3} textAnchor="end" className="atlas-tick">1e{value}</text></g>)}
      {[.01, .1, 1, 10, 70].map((value) => <g key={value} aria-hidden="true"><line x1={sx(value)} x2={sx(value)} y1={top} y2={top + h} stroke={colors.grid} /><text x={sx(value)} y={top + h + 17} textAnchor="middle" className="atlas-tick">{value}</text></g>)}
      <line x1={left} x2={width - right} y1={sy(-4)} y2={sy(-4)} stroke={colors.rust} strokeDasharray="5 4" /><text x={width - right} y={sy(-4) - 7} textAnchor="end" className="atlas-reference">1e−4 reference</text>
      <rect x={left} y={sy(-10.35) - 7} width={w} height={14} fill={colors.censored} opacity={.23} />
      {plotted.map((event, index) => <circle key={event.event_id} cx={sx(event.miss_distance_km)} cy={pointY(event, index)} r={event.pc_is_floored ? 1.8 : 2.2} fill={event.pc_is_floored ? colors.censored : event.dilution === 1 ? colors.rust : event.dilution === 0 ? colors.olive : colors.unavailable} opacity={event.pc_is_floored ? .5 : .75} onMouseEnter={() => setActive(index)}><title>{description(event)}</title></circle>)}
      {selected && <circle cx={sx(selected.miss_distance_km)} cy={pointY(selected, active)} r={6} fill="none" stroke={colors.unavailable} strokeWidth={1.8} pointerEvents="none" />}
      <text x={left + w / 2} y={height - 6} textAnchor="middle" className="atlas-axis-note">Miss distance · km · logarithmic scale</text>
    </svg>
    <p className="atlas-readout" role="status" aria-live="polite">{selected ? description(selected) : "No reported probabilities in this sample."}</p>
    <p className="atlas-keyboard-note">Focus the plot and use ← → to inspect. {count(events.length - plotted.length)} records without P<sub>c</sub> are omitted. The bottom band contains censored bounds.</p>
    <details className="atlas-values"><summary>Read all sample values <span aria-hidden="true">+</span></summary><div className="atlas-table-scroll"><table><caption>Display sample · exact values · rows {page * pageSize + 1}–{Math.min((page + 1) * pageSize, events.length)}</caption><thead><tr><th scope="col">Event</th><th scope="col">Miss · km</th><th scope="col">P<sub>c</sub></th><th scope="col">Dilution</th></tr></thead><tbody>{events.slice(page * pageSize, (page + 1) * pageSize).map((event) => <tr key={event.event_id}><th scope="row">{event.event_id}</th><td>{exact(event.miss_distance_km)}</td><td>{event.pc == null ? "Unavailable" : event.pc_is_floored ? "≤ 1e−10 (bound)" : String(event.pc)}</td><td>{event.dilution == null ? "Unknown" : event.dilution ? "Flagged" : "Unflagged"}</td></tr>)}</tbody></table></div><div className="atlas-pagination"><button disabled={page === 0} onClick={() => setPage((value) => value - 1)}>← Previous</button><span aria-live="polite">Page {page + 1} of {pageCount}</span><button disabled={page >= pageCount - 1} onClick={() => setPage((value) => value + 1)}>Next →</button></div></details>
  </>;
}

function DistributionFigure({ chart, index, population, events }: { chart: Chart; index: number; population: number; events: Event[] }) {
  const ref = useRef<HTMLElement>(null);
  const id = useId();
  useChartEntrance(ref);
  return <section className="atlas-figure" ref={ref} aria-labelledby={id}>
    <div className="atlas-figure-top"><span className="atlas-index">FIG. {String(index + 1).padStart(2, "0")}</span><span className={`atlas-scope atlas-${chart.scope}`}>{chart.scope === "population" ? "Full dataset" : "Display sample"} / {count(chart.scope === "population" ? population : events.length)}</span></div>
    <h3 id={id}>{chart.title}</h3><p className="atlas-note">{chart.note}</p>
    {chart.legend && <LegendRow items={chart.legend} />}
    {chart.scatter ? <ScatterPlot events={events} /> : <BarPlot bars={chart.bars ?? []} title={chart.title} logarithmic={chart.log} unit={chart.unit} />}
  </section>;
}

function buildCharts(summary: Summary, events: Event[]): Chart[] {
  const population = summary.population, sources = Object.entries(population.by_source);
  const merge = (key: "uncensored_decades" | "altitude_bands" | "covariance_trace_decades") => {
    const counts: Record<string, number> = {};
    sources.forEach(([, source]) => Object.entries(source[key] ?? {}).forEach(([label, value]) => { counts[label] = (counts[label] ?? 0) + value; }));
    return counts;
  };
  const decadeBars = (counts: Record<string, number>): Bar[] => Object.keys(counts).sort((a, b) => Number(a.split("..")[0]) - Number(b.split("..")[0])).map((range) => ({ label: range.split("..")[0], fullLabel: range.replace("..", " to < "), value: counts[range] }));
  const flagLegend = [{ label: "Unflagged", color: colors.olive }, { label: "Dilution flagged", color: colors.rust }];
  const charts: Chart[] = [
    { title: "The floor is a bound, not a probability.", scope: "population", note: "Reported probabilities are grouped into powers of ten. Censored entries are kept separate at the inferred 1e−10 reporting floor. The provider does not document this floor.", legend: [{ label: "Above floor", color: colors.olive }, { label: "Censored bound", color: colors.censored }, { label: "Unavailable", color: colors.unavailable }], bars: [{ label: "Censored", value: population.censored, color: colors.censored, emphasis: true }, ...decadeBars(merge("uncensored_decades")), { label: "No Pc", value: population.pc_null, color: colors.unavailable }] },
    { title: "Above the reference line.", scope: "population", note: "Pc ≥ 1e−4 is at least 1 in 10,000 under the model. The reference is distinct from the Kelvins agent’s 1e−7 invocation threshold. Neither is a universal action rule.", legend: flagLegend, log: false, bars: sources.flatMap(([name, source]) => [{ label: `${sourceName(name)} unflagged`, value: source.pc_by_dilution?.robust?.above_action_threshold ?? 0, color: colors.olive }, { label: `${sourceName(name)} flagged`, value: source.pc_by_dilution?.diluted?.above_action_threshold ?? 0, color: colors.rust }]) },
    { title: "When more uncertainty lowers Pc.", scope: "population", note: "In the dilution regime, broadening the position uncertainty can reduce the calculated collision probability. An absent flag does not establish that the covariance is accurate.", bars: sources.flatMap(([name, source]) => [{ label: `${sourceName(name)} unflagged`, value: source.dilution_values["0.0"] ?? 0, color: colors.olive }, { label: `${sourceName(name)} flagged`, value: source.dilution_values["1.0"] ?? 0, color: colors.rust }, { label: `${sourceName(name)} unknown`, value: source.dilution_values.NULL ?? 0, color: colors.unavailable }]) },
    { title: "The orbits behind the encounters.", scope: "population", note: "Altitude above a spherical Earth of radius 6,378.137 km. Each record contributes two object appearances, not two unique satellites. Lower orbits are more sensitive to atmospheric drag.", unit: "object appearances", bars: Object.entries(merge("altitude_bands")).map(([label, value]) => ({ label: label.replace(" km", "").replace(/\(.*\)/, "").trim(), fullLabel: label, value })) },
  ];
  const quartiles: { key: "miss_distance_km" | "relative_speed_kms" | "mahalanobis_distance"; title: string; note: string; unit: string }[] = [
    { key: "miss_distance_km", title: "How close do they pass?", note: "Miss distance is the predicted separation at closest approach.", unit: "km" },
    { key: "relative_speed_kms", title: "How fast is the encounter?", note: "Relative speed measures how quickly one object moves past the other.", unit: "km/s" },
    { key: "mahalanobis_distance", title: "Separation, relative to uncertainty.", note: "Mahalanobis distance accounts for the size and direction of position uncertainty. It has no physical unit.", unit: "dimensionless" },
  ];
  quartiles.forEach((quartile) => charts.push({ title: quartile.title, scope: "population", note: `${quartile.note} Each source shows its minimum, Q1 (25%), median, Q3 (75%) and maximum. Dark outlines identify medians.`, unit: quartile.unit, log: true, legend: [{ label: "Spherical", color: colors.olive }, { label: "SFSH", color: colors.rust }], bars: sources.flatMap(([name, source]) => (["min", "q1", "median", "q3", "max"] as const).map((stat) => ({ label: `${sourceName(name)} ${stat}`, value: source[quartile.key][stat], color: name === "spherical" ? colors.olive : colors.rust, emphasis: stat === "median" }))) }));
  charts.push({ title: "Uncertainty spans orders of magnitude.", scope: "population", note: "Covariance trace adds the three position variances, in km². For a valid covariance, it bounds the largest eigenvalue. Labels give the lower edge of each decade; counts refer to object appearances.", unit: "object appearances", bars: decadeBars(merge("covariance_trace_decades")) });
  charts.push({ title: "A close pass is only part of the story.", scope: "sample", note: "Compare miss distance with calculated probability. High-Pc cases were deliberately over-sampled; point density does not show their population prevalence. Censored bounds occupy their own band.", legend: [...flagLegend, { label: "Censored bound", color: colors.censored }, { label: "Unknown flag", color: colors.unavailable }], scatter: true });
  const classes: Record<string, number> = {};
  events.forEach((event) => { const key = event.stratum.split("|")[1]; classes[key] = (classes[key] ?? 0) + 1; });
  const labels: Record<string, string> = { action: "≥ 1e−4", near_threshold: "1e−6 to < 1e−4", moderate: "1e−8 to < 1e−6", low: "< 1e−8", censored: "Censored", null: "No Pc" };
  charts.push({ title: "What the display chooses to show.", scope: "sample", note: "The six sampling categories keep rare cases visible. Compare this composition with Figure 01 before drawing conclusions about frequency. The lowest reported Pc group excludes censored bounds.", log: false, bars: ["action", "near_threshold", "moderate", "low", "censored", "null"].filter((key) => classes[key]).map((key) => ({ label: labels[key], value: classes[key], color: key === "censored" ? colors.censored : key === "null" ? colors.unavailable : key === "action" ? colors.rust : colors.olive })) });
  return charts;
}

export default function DistributionAtlas() {
  const [data, setData] = useState<{ summary: Summary; events: Event[] } | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const read = async (path: string) => { const response = await fetch(path, { signal: controller.signal }); if (!response.ok) throw new Error(`Could not read ${path}.`); return response.json(); };
    Promise.all([read("/data/summary.json"), read("/data/events.json")]).then(([summary, events]: [Summary, Event[]]) => {
      if (!summary?.population?.by_source || !Array.isArray(events)) throw new Error("The distribution export has an unexpected format.");
      setData({ summary, events }); setError("");
    }).catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [attempt]);
  const charts = useMemo(() => data ? buildCharts(data.summary, data.events) : [], [data]);
  if (error) return <section className="distribution-atlas atlas-error"><p className="eyebrow">Distribution atlas</p><h2>The data could not be read.</h2><p role="alert">{error}</p><button className="button button-dark" onClick={() => { setError(""); setAttempt((value) => value + 1); }}>Reload data</button></section>;
  if (!data) return <section className="distribution-atlas" aria-busy="true"><p className="eyebrow">Distribution atlas</p><h2>Reading the population.</h2><p role="status">Loading the complete summary and display sample…</p></section>;
  const population = data.summary.population;
  return <div className="distribution-atlas">
    <header className="atlas-intro"><div><p className="eyebrow">A field guide to the data</p><h2>The sample is<br /><em>not the population.</em></h2><p>The display makes rare encounters visible. These ten views give them context, keeping reported values, censored bounds and missing probabilities distinct.</p></div><div className="atlas-fact"><strong>{(100 * population.censored / population.events).toFixed(1)}<span>%</span></strong><p>of ingested records sit at the inferred probability floor.</p><span className="atlas-fact-note">A bound is not an exact measurement.</span></div></header>
    <div className="atlas-population-line"><span><strong>{count(population.events)}</strong> ingested records</span><span><strong>{count(data.events.length)}</strong> sampled records</span><span><strong>{count(population.above_action_threshold)}</strong> records with P<sub>c</sub> ≥ 10<sup>−4</sup></span><span><strong>{count(population.pc_null)}</strong> unavailable probabilities</span></div>
    <p className="atlas-boundary">The Spherical and SFSH files can contain overlapping encounters. Counts describe ingested records and object appearances, not unique satellites or a live orbital population. All chart values are static exports; scene filters do not change them.</p>
    <div className="atlas-grid">{charts.map((chart, index) => <DistributionFigure key={chart.title} chart={chart} index={index} population={population.events} events={data.events} />)}</div>
    <footer className="atlas-footer"><span className="eyebrow">Know what each mark means.</span><p>Full-dataset charts use the processed population summary. Sample charts use the same {count(data.events.length)} records as the 3D scene. A small calculated probability is conditional on the supplied uncertainty model; it does not establish orbital safety.</p></footer>
  </div>;
}
