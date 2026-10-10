"use client";

import { useEffect, useRef, useState } from "react";
import { fixed, palette, percent, reusedIn, signed, type Condition, type Decision, type DevelopmentBank, type LossSummary, type Rate, type RealContrast, type RealMetric } from "@/lib/findings";

type Tip = { left: number; top: number; title: string; lines: string[] } | null;

const scale = (domain: [number, number], range: [number, number]) => (value: number) =>
  range[0] + (value - domain[0]) / (domain[1] - domain[0]) * (range[1] - range[0]);

const ticks = (from: number, to: number, step: number) => {
  const values: number[] = [];
  for (let value = Math.ceil(from / step) * step; value <= to + step / 1e6; value += step) values.push(Number(value.toFixed(6)));
  return values;
};

/** Charts render at their container's width so text keeps one size; hover and focus share one tooltip. */
function useChart(minWidth = 300) {
  const host = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [tip, setTip] = useState<Tip>(null);
  useEffect(() => {
    const node = host.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(minWidth, Math.round(entry.contentRect.width))));
    observer.observe(node);
    return () => observer.disconnect();
  }, [minWidth]);
  const show = (target: Element, title: string, lines: string[]) => {
    const box = host.current?.getBoundingClientRect();
    const mark = target.getBoundingClientRect();
    if (!box) return;
    setTip({ left: mark.left + mark.width / 2 - box.left, top: mark.top - box.top, title, lines });
  };
  const bind = (title: string, lines: string[]) => ({
    tabIndex: 0,
    onPointerEnter: (event: React.PointerEvent<SVGElement>) => show(event.currentTarget, title, lines),
    onFocus: (event: React.FocusEvent<SVGElement>) => show(event.currentTarget, title, lines),
    onPointerLeave: () => setTip(null),
    onBlur: () => setTip(null),
    "aria-label": `${title}. ${lines.join(". ")}`,
  });
  const overlay = tip && <div className="fd-tip" role="status" style={{ left: tip.left, top: tip.top }}><strong>{tip.title}</strong>{tip.lines.map((line) => <span key={line}>{line}</span>)}</div>;
  return { host, width, bind, overlay };
}

export function ValuesTable({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  return <details className="fd-values"><summary>View exact values</summary><div className="table-wrap"><table><caption>{caption}</caption><thead><tr>{head.map((cell) => <th key={cell} scope="col">{cell}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{row.map((cell, column) => column === 0 ? <th key={column} scope="row">{cell}</th> : <td key={column}>{cell}</td>)}</tr>)}</tbody></table></div></details>;
}

/* ------------------------------------------------------------------ windows */

export function WindowsDiagram({ condition, message, onMessage, highlight, onHighlight }: {
  condition: Condition; message: number; onMessage: (index: number) => void; highlight: number | null; onHighlight: (id: number | null) => void;
}) {
  const { host, width } = useChart();
  const left = 52, cell = (width - left - 8) / 60, row = 30, top = 22;
  const height = top + row * 6 + 34;
  const earlier = (index: number) => new Set(condition.windows.slice(0, index).flat());
  return <div className="fd-chart" ref={host}><div className="fd-chart-scroll"><svg className="fd-svg fd-windows" viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Observation windows of the six messages under ${condition.label}`}>
    {[0, 10, 20, 30, 40, 50, 60].map((id) => <text key={id} className="fd-axis-text" x={left + id * cell} y={14} textAnchor="middle">{id}</text>)}
    {highlight != null && highlight < 60 && <rect x={left + highlight * cell - 1} y={top - 4} width={cell + 2} height={row * 6 + 6} className="fd-column-focus" />}
    {condition.windows.map((window, index) => {
      const before = earlier(index);
      const y = top + index * row;
      const repeated = reusedIn(condition.windows, index).length;
      return <g key={index} className={`fd-window-row ${index === message ? "is-selected" : ""}`} role="button" tabIndex={0} aria-pressed={index === message}
        aria-label={`Message m${index + 1}: observations ${window[0]} to ${window[window.length - 1]}, ${window.length} in total, ${repeated} already used by an earlier message`}
        onClick={() => onMessage(index)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onMessage(index); } }}>
        <rect x={0} y={y} width={width} height={row} className="fd-row-hit" />
        <text x={8} y={y + row / 2 + 4} className="fd-row-label">m{index + 1}</text>
        {Array.from({ length: 60 }, (_, id) => {
          const inside = window.includes(id);
          const fill = inside ? (before.has(id) ? palette.reused : palette.fresh) : "#e6e1d5";
          return <rect key={id} x={left + id * cell + 1} y={y + 6} width={cell - 2} height={row - 12} rx={1.5} fill={fill}
            onPointerEnter={() => onHighlight(id)} onPointerLeave={() => onHighlight(null)} />;
        })}
      </g>;
    })}
    <text x={left} y={height - 8} className="fd-axis-text">{width < 520 ? "Observation ID (0–59 visible)" : "Observation ID (0–59 visible to messages; 60–79 arrive after the two-day cutoff)"}</text>
  </svg></div></div>;
}

/* ------------------------------------------------------------ overlap response */

const RESPONSE = ["no_reuse", "overlap_50", "overlap_90", "solution_reissue"] as const;
const RESPONSE_LABEL: Record<string, string> = { no_reuse: "No reuse", overlap_50: "50% overlap", overlap_90: "90% overlap", solution_reissue: "Solution reissue" };
const SHORT_LABEL: Record<string, string> = { no_reuse: "None", overlap_50: "50%", overlap_90: "90%", solution_reissue: "Reissue" };
const SERIES = [
  { arm: "grouped", label: "Grouped history", color: palette.context, emphasis: false },
  { arm: "oracle_lineage_weight", label: "Lineage-weighted", color: palette.context, emphasis: false },
  { arm: "latest_metadata", label: "Latest message", color: palette.fresh, emphasis: true },
  { arm: "singleton", label: "History summary", color: palette.reused, emphasis: true },
];

export function OverlapChart({ losses, selected, onSelect }: { losses: LossSummary[]; selected: string; onSelect: (condition: string) => void }) {
  const { host, width, bind, overlay } = useChart();
  const compact = width < 520;
  const height = Math.round(Math.min(420, Math.max(300, width * .36))), left = 58, right = compact ? 22 : 130, top = 20, bottom = 56;
  const band = Math.min(92, (width - left - right) / 3 * .9);
  const x = (index: number) => left + index * (width - left - right) / 3;
  const y = scale([0, 0.18], [height - bottom, top]);
  const find = (arm: string, condition: string) => losses.find((item) => item.arm === arm && item.condition === condition)!;
  return <div className="fd-chart" ref={host}>
    <div className="fd-legend"><span><i style={{ background: palette.reused }} />History summary</span><span><i style={{ background: palette.fresh }} />Latest message (comparator)</span><span><i style={{ background: palette.context }} />Grouped and lineage-weighted history</span></div>
    <div className="fd-chart-scroll"><svg className="fd-svg" viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Mean clipped log loss by reuse condition for four forecasters">
      {ticks(0, 0.18, 0.03).map((value) => <g key={value} className="fd-axis"><line x1={left} x2={width - right + 10} y1={y(value)} y2={y(value)} className="fd-grid" /><text x={left - 10} y={y(value) + 4} textAnchor="end">{value.toFixed(2)}</text></g>)}
      <text className="fd-axis-title" transform={`translate(14 ${top + (height - top - bottom) / 2}) rotate(-90)`} textAnchor="middle">Mean clipped log loss (nats)</text>
      {RESPONSE.map((condition, index) => <g key={condition}>
        <rect x={x(index) - band / 2} y={top} width={band} height={height - top - bottom} className={`fd-band ${condition === selected ? "is-selected" : ""}`} onClick={() => onSelect(condition)}
          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(condition); } }}
          {...bind(RESPONSE_LABEL[condition], SERIES.slice().reverse().map((series) => { const item = find(series.arm, condition); return `${series.label}: ${fixed(item.mean, 4)}${series.emphasis ? ` (banks ${fixed(item.min, 3)}–${fixed(item.max, 3)})` : ""}`; }))} />
        <text x={x(index)} y={height - bottom + 22} textAnchor="middle" className={`fd-axis-text ${condition === selected ? "is-strong" : ""}`}>{compact ? SHORT_LABEL[condition] : RESPONSE_LABEL[condition]}</text>
      </g>)}
      {SERIES.map((series) => {
        const points = RESPONSE.map((condition, index) => [x(index), y(find(series.arm, condition).mean)] as const);
        return <g key={series.arm}>
          <polyline points={points.map((point) => point.join(",")).join(" ")} fill="none" stroke={series.color} strokeWidth={series.emphasis ? 2 : 1.25} strokeLinejoin="round" strokeLinecap="round" />
          {series.emphasis && RESPONSE.map((condition, index) => { const item = find(series.arm, condition); return <line key={condition} x1={x(index)} x2={x(index)} y1={y(item.min)} y2={y(item.max)} stroke={series.color} strokeWidth={1} opacity={0.6} />; })}
          {RESPONSE.map((condition, index) => {
            const item = find(series.arm, condition);
            return <circle key={condition} cx={x(index)} cy={y(item.mean)} r={series.emphasis ? 5 : 3.5} fill={series.color} stroke="#f5f1e8" strokeWidth={2} className="fd-passive" />;
          })}
        </g>;
      })}
      {!compact && <text x={x(3) + 14} y={y(find("singleton", "solution_reissue").mean) - 8} className="fd-direct">History summary</text>}
      {!compact && <text x={x(3) + 14} y={y(find("latest_metadata", "solution_reissue").mean) + 14} className="fd-direct">Latest message</text>}
    </svg></div>
    {overlay}
  </div>;
}

/* ---------------------------------------------------------------- decision rule */

export function DecisionRule({ p1, margin }: { p1: Decision; margin: number }) {
  const [hypothetical, setHypothetical] = useState(false);
  const { host, width } = useChart();
  const height = hypothetical ? 210 : 132, left = 30, right = 30;
  const x = scale([-0.02, 0.1], [left, width - right]);
  const examples = [
    { label: "Would read as inconclusive", lower: 0.011, upper: 0.034, y: 128 },
    { label: "Would read as not material", lower: -0.006, upper: 0.015, y: 162 },
  ];
  return <div className="fd-chart" ref={host}>
    <div className="fd-chart-scroll"><svg className="fd-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Decision rule: the frozen 95% interval for P1, ${fixed(p1.lower)} to ${fixed(p1.upper)}, lies entirely above the margin of ${margin}; material degradation is confirmed.`}>
      <rect x={x(margin)} y={18} width={x(0.1) - x(margin)} height={height - 52} className="fd-zone-confirm" />
      {ticks(-0.02, 0.1, 0.02).map((value) => <g key={value} className="fd-axis"><line x1={x(value)} x2={x(value)} y1={18} y2={height - 34} className="fd-grid" /><text x={x(value)} y={height - 18} textAnchor="middle">{fixed(value, 2)}</text></g>)}
      <line x1={x(margin)} x2={x(margin)} y1={10} y2={height - 34} className="fd-margin" />
      <text x={x(margin) - 8} y={30} textAnchor="end" className="fd-axis-text is-strong">Margin {margin}</text>
      {width >= 520 && <text x={x(0.1) - 8} y={32} textAnchor="end" className="fd-axis-text">Confirm zone: whole interval above the margin</text>}
      <line x1={x(p1.lower)} x2={x(p1.upper)} y1={70} y2={70} stroke={palette.reused} strokeWidth={4} strokeLinecap="round" />
      <circle cx={x(p1.mean)} cy={70} r={7} fill={palette.reused} stroke="#f5f1e8" strokeWidth={2} />
      <text x={x(p1.mean)} y={96} textAnchor="middle" className="fd-direct">P1 = {fixed(p1.mean)} [{fixed(p1.lower)}, {fixed(p1.upper)}]</text>
      {hypothetical && examples.map((example) => <g key={example.label} opacity={0.65}>
        <line x1={x(example.lower)} x2={x(example.upper)} y1={example.y} y2={example.y} stroke={palette.context} strokeWidth={3} strokeDasharray="5 4" />
        {width >= 520
          ? <text x={x(example.upper) + 10} y={example.y + 4} className="fd-axis-text">{example.label} (hypothetical)</text>
          : <text x={x(example.lower)} y={example.y + 16} className="fd-axis-text">{example.label}</text>}
      </g>)}
    </svg></div>
    <button className="fd-link-button" onClick={() => setHypothetical((value) => !value)} aria-pressed={hypothetical}>{hypothetical ? "Hide the other outcomes" : "How would other intervals have been read?"}</button>
  </div>;
}

/* ------------------------------------------------------------------ forest plot */

const CONTRAST_TEXT: Record<string, { name: string; question: string }> = {
  P1: { name: "P1 · degradation at 90% overlap", question: "How much worse does the history summary get at 90% overlap, relative to the latest message?" },
  S5: { name: "S5 · degradation under solution reissue", question: "The same question when one solution is republished six times." },
  S1: { name: "S1 · advantage left at 90% overlap", question: "Does the history summary keep any advantage over the latest message at 90% overlap?" },
  S2: { name: "S2 · grouped minus history summary", question: "Does label-free grouping reduce the degradation by more than 0.01?" },
  S3: { name: "S3 · lineage weights minus history summary", question: "Does weighting messages with the true observation lineage reduce it by more than 0.01?" },
  S6: { name: "S6 · history minus latest, reissue (exploratory)", question: "Under solution reissue, is the history summary worse than the latest message?" },
};

export function ForestPlot({ decisions, selected, onSelect }: { decisions: Decision[]; selected: string; onSelect: (id: string) => void }) {
  const { host, width, bind, overlay } = useChart();
  const compact = width < 520;
  const row = compact ? 58 : 44, top = 14, left = compact ? 14 : 250, right = 24;
  const height = top + row * decisions.length + 40;
  const x = scale([-0.03, 0.1], [left, width - right]);
  return <div className="fd-chart" ref={host}>
    <div className="fd-chart-scroll"><svg className="fd-svg" viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Frozen contrasts with their 95% intervals and null values">
      {ticks(-0.02, 0.1, 0.02).map((value) => <g key={value} className="fd-axis"><line x1={x(value)} x2={x(value)} y1={top} y2={height - 34} className="fd-grid" /><text x={x(value)} y={height - 18} textAnchor="middle">{fixed(value, 2)}</text></g>)}
      <line x1={x(0)} x2={x(0)} y1={top} y2={height - 34} className="fd-zero" />
      {decisions.map((item, index) => {
        const middle = top + index * row + row / 2;
        const y = compact ? middle + 10 : middle;
        const exploratory = item.role === "exploratory";
        const color = exploratory ? palette.context : palette.reused;
        const verdict = item.decision ? "Material degradation confirmed" : item.holm_rejected ? "Holm rejects the null" : "Exploratory, not tested";
        return <g key={item.id} className={`fd-forest-row ${item.id === selected ? "is-selected" : ""}`} onClick={() => onSelect(item.id)}>
          <rect x={0} y={middle - row / 2} width={width} height={row} className="fd-row-hit" />
          <text x={8} y={compact ? middle - 12 : y + 4} className="fd-row-label">{CONTRAST_TEXT[item.id].name}</text>
          <line x1={x(item.lower)} x2={x(item.upper)} y1={y} y2={y} stroke={color} strokeWidth={2.5} strokeLinecap="round" />
          {item.null != null && <line x1={x(item.null)} x2={x(item.null)} y1={y - 9} y2={y + 9} className="fd-null" />}
          <circle cx={x(item.mean)} cy={y} r={5.5} fill={color} stroke="#f5f1e8" strokeWidth={2} className="fd-mark"
            {...bind(CONTRAST_TEXT[item.id].name, [`Estimate ${signed(item.mean, 4)}`, `95% interval ${signed(item.lower, 4)} to ${signed(item.upper, 4)}`, item.null != null ? `Null ${signed(item.null, 2)}` : "No null: exploratory", verdict])}
            onKeyDown={(event) => { if (event.key === "Enter") onSelect(item.id); }} />
        </g>;
      })}
      <text x={left} y={height - 2} className="fd-axis-text">{compact ? "Difference (nats) · tick = null" : "Difference in mean clipped log loss (nats) · vertical tick = null value"}</text>
    </svg></div>
    {overlay}
  </div>;
}

export function contrastQuestion(id: string) { return CONTRAST_TEXT[id]?.question ?? ""; }
export function contrastName(id: string) { return CONTRAST_TEXT[id]?.name ?? id; }

/* ------------------------------------------------------------------- bank strip */

export function BankStrip({ values, mean, margin, label }: { values: { bank: string; mean: number }[]; mean: number; margin: number | null; label: string }) {
  const { host, width, bind, overlay } = useChart();
  const height = 112, left = 24, right = 24;
  const low = Math.min(...values.map((item) => item.mean), margin ?? 0, 0) - 0.01;
  const high = Math.max(...values.map((item) => item.mean), margin ?? 0) + 0.01;
  const step = high - low > 0.06 ? 0.02 : 0.01;
  const x = scale([low, high], [left, width - right]);
  return <div className="fd-chart" ref={host}>
    <div className="fd-chart-scroll"><svg className="fd-svg" viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`${label}: one dot per independent training bank`}>
      {ticks(low, high, step).map((value) => <g key={value} className="fd-axis"><line x1={x(value)} x2={x(value)} y1={14} y2={height - 34} className="fd-grid" /><text x={x(value)} y={height - 16} textAnchor="middle">{fixed(value, 2)}</text></g>)}
      {margin != null && <line x1={x(margin)} x2={x(margin)} y1={10} y2={height - 34} className="fd-margin" />}
      <line x1={x(mean)} x2={x(mean)} y1={18} y2={height - 38} className="fd-mean" />
      {values.map((item, index) => <circle key={item.bank} cx={x(item.mean)} cy={46 + (index % 2) * 14} r={6} fill={palette.reused} fillOpacity={0.85} stroke="#f5f1e8" strokeWidth={2} className="fd-mark"
        {...bind(`Training bank ${item.bank}`, [`Mean over 5,000 scenarios: ${signed(item.mean, 4)}`])} />)}
    </svg></div>
    {overlay}
  </div>;
}

/* --------------------------------------------------------------- miss dumbbell */

export function MissDumbbell({ rates }: { rates: Rate[] }) {
  const { host, width, bind, overlay } = useChart();
  const arms = [["singleton", "History summary"], ["grouped", "Grouped history"], ["oracle_lineage_weight", "Lineage-weighted"], ["latest_metadata", "Latest message"]];
  const compact = width < 520;
  const row = compact ? 54 : 38, top = 12, left = compact ? 14 : 170, right = compact ? 20 : 40;
  const height = top + row * arms.length + 40;
  const x = scale([0, 0.12], [left, width - right]);
  const rate = (arm: string, condition: string) => rates.find((item) => item.arm === arm && item.condition === condition)!.miss_rate;
  return <div className="fd-chart" ref={host}>
    <div className="fd-legend"><span><i className="fd-hollow" />Without reuse</span><span><i style={{ background: palette.reused }} />At 90% overlap</span></div>
    <div className="fd-chart-scroll"><svg className="fd-svg" viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Share of positives missed at the nominal 95% recall threshold, without reuse and at 90% overlap">
      {ticks(0, 0.12, 0.02).map((value) => <g key={value} className="fd-axis"><line x1={x(value)} x2={x(value)} y1={top} y2={height - 34} className="fd-grid" /><text x={x(value)} y={height - 18} textAnchor="middle">{percent(value, 0)}</text></g>)}
      {arms.map(([arm, label], index) => {
        const middle = top + index * row + row / 2;
        const y = compact ? middle + 10 : middle;
        const before = rate(arm, "no_reuse"), after = rate(arm, "overlap_90");
        return <g key={arm}>
          <text x={8} y={compact ? middle - 10 : y + 4} className="fd-row-label">{label}</text>
          <line x1={x(before)} x2={x(after)} y1={y} y2={y} stroke={palette.context} strokeWidth={2} />
          <circle cx={x(before)} cy={y} r={5.5} fill="#f5f1e8" stroke={palette.ink} strokeWidth={1.5} className="fd-mark" {...bind(`${label} · without reuse`, [`Missed ${percent(before)} of positives`])} />
          <circle cx={x(after)} cy={y} r={5.5} fill={palette.reused} stroke="#f5f1e8" strokeWidth={2} className="fd-mark" {...bind(`${label} · 90% overlap`, [`Missed ${percent(after)} of positives`])} />
        </g>;
      })}
      <text x={left} y={height - 2} className="fd-axis-text">{compact ? "Share of high-risk scenarios missed" : "Share of high-risk scenarios missed at the nominal 95% recall threshold"}</text>
    </svg></div>
    {overlay}
  </div>;
}

/* ----------------------------------------------------------- development banks */

export function DevelopmentChart({ banks, margin }: { banks: DevelopmentBank[]; margin: number }) {
  const { host, width, bind, overlay } = useChart();
  const groups = Array.from(new Set(banks.map((item) => item.configuration)));
  const height = Math.round(Math.min(380, Math.max(290, width * .3))), left = 52, top = 18, bottom = 50;
  const band = (width - left - 16) / groups.length;
  const y = scale([0, 0.1], [height - bottom, top]);
  return <div className="fd-chart" ref={host}>
    <div className="fd-chart-scroll"><svg className="fd-svg" viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Primary contrast per independent development training bank, by simulator configuration">
      {ticks(0, 0.1, 0.02).map((value) => <g key={value} className="fd-axis"><line x1={left} x2={width - 10} y1={y(value)} y2={y(value)} className="fd-grid" /><text x={left - 10} y={y(value) + 4} textAnchor="end">{value.toFixed(2)}</text></g>)}
      <line x1={left} x2={width - 10} y1={y(margin)} y2={y(margin)} className="fd-margin" />
      <text x={left + 6} y={y(margin) - 6} className="fd-axis-text is-strong">Margin {margin}</text>
      {groups.map((group, groupIndex) => {
        const members = banks.filter((item) => item.configuration === group);
        const centre = left + band * groupIndex + band / 2;
        return <g key={group}>
          <text x={centre} y={height - bottom + 22} textAnchor="middle" className="fd-axis-text">{width < 520 ? SHORT_CONFIG[group] ?? group : group}</text>
          {members.map((item, index) => {
            const cx = centre + (index - (members.length - 1) / 2) * 14;
            return <g key={item.bank}>
              <line x1={cx} x2={cx} y1={y(item.lower)} y2={y(item.upper)} stroke={palette.reused} strokeWidth={1.25} opacity={0.55} />
              <circle cx={cx} cy={y(item.mean)} r={4.5} fill={palette.reused} stroke="#f5f1e8" strokeWidth={1.5} className="fd-mark"
                {...bind(`${group} · bank ${item.bank}`, [`P1 ${signed(item.mean, 4)}`, `Per-bank interval ${signed(item.lower, 3)} to ${signed(item.upper, 3)}`])} />
            </g>;
          })}
        </g>;
      })}
      <text className="fd-axis-title" transform={`translate(14 ${top + (height - top - bottom) / 2}) rotate(-90)`} textAnchor="middle">P1 per training bank (nats)</text>
    </svg></div>
    {overlay}
  </div>;
}

const SHORT_CONFIG: Record<string, string> = { Isotropic: "Iso", "Anisotropy 2": "Aniso 2", "Anisotropy 8": "Aniso 8", "Doubled noise": "Noise ×2", "Shared bias": "Bias" };

/* ----------------------------------------------------------- real-data charts */

const REAL_TEXT: Record<string, string> = { R1: "R1 · history summary − latest metadata", R2: "R2 · grouped − history summary", R3: "R3 · latest metadata − latest risk", R4: "R4 · gradient boosting − latest metadata" };

export function RealContrastChart({ contrasts, split }: { contrasts: RealContrast[]; split: string }) {
  const { host, width, bind, overlay } = useChart();
  const rows = ["R1", "R2", "R3", "R4"].map((id) => contrasts.find((item) => item.id === id && item.split === split) ?? null);
  const span = split === "training_oof" ? 0.008 : 0.07;
  const compact = width < 520;
  const row = compact ? 62 : 46, top = 12, left = compact ? 14 : 250, right = 24;
  const height = top + row * rows.length + 40;
  const x = scale([-span, span], [left, width - right]);
  return <div className="fd-chart" ref={host}>
    <div className="fd-legend"><span><i style={{ background: palette.ink }} />Event-level 95% interval</span><span><i style={{ background: palette.context }} />Mission-cluster 95% interval</span></div>
    <div className="fd-chart-scroll"><svg className="fd-svg" viewBox={`0 0 ${width} ${height}`} role="group" aria-label="Paired contrasts on real conjunction data messages">
      {ticks(-span, span, span / 2).map((value) => <g key={value} className="fd-axis"><line x1={x(value)} x2={x(value)} y1={top} y2={height - 34} className="fd-grid" /><text x={x(value)} y={height - 18} textAnchor="middle">{signed(value, split === "training_oof" ? 3 : 2)}</text></g>)}
      <line x1={x(0)} x2={x(0)} y1={top} y2={height - 34} className="fd-zero" />
      {rows.map((item, index) => {
        const middle = top + index * row + row / 2;
        const y = compact ? middle + 12 : middle;
        const labelY = compact ? middle - 14 : y + 4;
        const id = ["R1", "R2", "R3", "R4"][index];
        if (!item) return <g key={id}><text x={8} y={labelY} className="fd-row-label">{REAL_TEXT[id]}</text><text x={x(0) + 8} y={y + 4} className="fd-axis-text">not evaluated on this split</text></g>;
        return <g key={id}>
          <text x={8} y={labelY} className="fd-row-label">{REAL_TEXT[id]}</text>
          <line x1={x(item.mission_lower)} x2={x(item.mission_upper)} y1={y - 7} y2={y - 7} stroke={palette.context} strokeWidth={2} />
          <line x1={x(item.event_lower)} x2={x(item.event_upper)} y1={y + 5} y2={y + 5} stroke={palette.ink} strokeWidth={2.5} />
          <circle cx={x(item.mean)} cy={y + 5} r={5} fill={palette.ink} stroke="#f5f1e8" strokeWidth={2} className="fd-mark"
            {...bind(REAL_TEXT[id], [`Mean difference ${signed(item.mean, 4)} nats`, `Event interval ${signed(item.event_lower, 4)} to ${signed(item.event_upper, 4)}`, `Mission interval ${signed(item.mission_lower, 4)} to ${signed(item.mission_upper, 4)} (${item.missions} missions)`])} />
        </g>;
      })}
      <text x={left} y={height - 2} className="fd-axis-text">Positive values favour the comparator (second arm)</text>
    </svg></div>
    {overlay}
  </div>;
}

export function FrontierChart({ curves, metrics, split }: { curves: Record<string, [number, number][]>; metrics: RealMetric[]; split: string }) {
  const { host, width, bind, overlay } = useChart();
  const series = [
    { arm: "latest", label: "Latest risk", color: palette.context, emphasis: false },
    { arm: "grouped", label: "Grouped history", color: palette.context, emphasis: false },
    { arm: "causal_gbm", label: "Gradient boosting", color: "#8a8574", emphasis: false },
    { arm: "latest_metadata", label: "Latest message", color: palette.fresh, emphasis: true },
    { arm: "singleton", label: "History summary", color: palette.reused, emphasis: true },
  ].filter((item) => curves[item.arm]);
  const positives = metrics.find((item) => item.split === split)?.positives ?? 1;
  const height = 320, left = 56, right = 24, top = 16, bottom = 52;
  const x = scale([0, 0.6], [left, width - right]);
  const y = scale([0, positives], [height - bottom, top]);
  const step = positives > 100 ? 25 : 10;
  const path = (points: [number, number][]) => {
    let d = "";
    let previous: [number, number] | null = null;
    for (const [fraction, missed] of points) {
      if (fraction > 0.6) break;
      const px = x(fraction), py = y(missed);
      d += previous ? ` H${px.toFixed(1)} V${py.toFixed(1)}` : `M${px.toFixed(1)},${py.toFixed(1)}`;
      previous = [fraction, missed];
    }
    return d;
  };
  return <div className="fd-chart" ref={host}>
    <div className="fd-legend"><span><i style={{ background: palette.reused }} />History summary</span><span><i style={{ background: palette.fresh }} />Latest message</span><span><i style={{ background: palette.context }} />Other arms</span></div>
    <div className="fd-chart-scroll"><svg className="fd-svg" viewBox={`0 0 ${width} ${height}`} role="group" aria-label={`Missed positives against the fraction of events reviewed, ${split === "training_oof" ? "training cohort out of fold" : "historical test split"}`}>
      {ticks(0, 0.6, 0.1).map((value) => <g key={value} className="fd-axis"><line x1={x(value)} x2={x(value)} y1={top} y2={height - bottom} className="fd-grid" /><text x={x(value)} y={height - bottom + 18} textAnchor="middle">{percent(value, 0)}</text></g>)}
      {ticks(0, positives, step).map((value) => <g key={value} className="fd-axis"><line x1={left} x2={width - right} y1={y(value)} y2={y(value)} className="fd-grid" /><text x={left - 10} y={y(value) + 4} textAnchor="end">{value}</text></g>)}
      <text x={left + (width - left - right) / 2} y={height - 10} textAnchor="middle" className="fd-axis-title">Fraction of events reviewed</text>
      <text className="fd-axis-title" transform={`translate(14 ${top + (height - top - bottom) / 2}) rotate(-90)`} textAnchor="middle">Missed positives (of {positives})</text>
      {series.map((item) => <path key={item.arm} d={path(curves[item.arm])} fill="none" stroke={item.color} strokeWidth={item.emphasis ? 2 : 1.25} strokeLinejoin="round" />)}
      {series.filter((item) => item.emphasis || item.arm === "causal_gbm").map((item) => {
        const metric = metrics.find((row) => row.split === split && row.arm === item.arm);
        if (!metric) return null;
        const fraction = metric.reviewed_95 / metric.n;
        return <circle key={item.arm} cx={x(fraction)} cy={y(metric.missed_95)} r={5.5} fill={item.color} stroke="#f5f1e8" strokeWidth={2} className="fd-mark"
          {...bind(`${item.label} · nominal 95% threshold`, [`Reviews ${percent(fraction)} of events`, `Misses ${metric.missed_95} of ${metric.positives} positives`])} />;
      })}
    </svg></div>
    {overlay}
  </div>;
}
