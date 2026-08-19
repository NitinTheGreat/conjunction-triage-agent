/**
 * Distribution charts, drawn as hand-built SVG. No charting library, no CDN.
 *
 * Every chart declares its scope — POPULATION (all 1,196,860 ingested events, via
 * summary.json) or SAMPLE (the 2,000 stratified events actually rendered in 3D). The two
 * are never mixed inside one chart, because the sample deliberately over-represents rare
 * high-probability events and reading a dataset proportion off it would be wrong.
 *
 * Censored Pc is always drawn as a separate labelled bar, never merged into the
 * histogram: it is a bound at the 1e-10 floor, not a measurement.
 */

const NS = 'http://www.w3.org/2000/svg';

const COLOURS = {
  bar: '#5eb0ff',
  censored: '#8891a8',
  nullPc: '#b26bd8',
  robust: '#35d0a5',
  diluted: '#ffb638',
  grid: '#232a3d',
  ink: '#98a0b8',
};

function el(name, attrs = {}, parent = null) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}

function card(container, title, scope, note) {
  const wrap = document.createElement('div');
  wrap.className = 'card';
  wrap.innerHTML =
    `<h3>${title}</h3><span class="scope ${scope}">${scope === 'population'
      ? 'population · all 1,196,860 events'
      : 'sample · 2,000 events'}</span>` + (note ? `<p class="note">${note}</p>` : '');
  container.appendChild(wrap);
  return wrap;
}

/** Compact bar label. Values here span counts in the millions and physical quantities
 *  below 0.01, so both ends need trimming or the labels collide with the axis. */
const shorten = (n) => {
  if (n === 0) return '0';
  const a = Math.abs(n);
  if (a >= 1e6) return `${(n / 1e6).toFixed(a >= 1e7 ? 0 : 1)}M`;
  if (a >= 1e3) return `${(n / 1e3).toFixed(a >= 1e4 ? 0 : 1)}k`;
  if (a >= 1) return String(Number(n.toFixed(a >= 100 ? 0 : 2)));
  if (a >= 0.01) return String(Number(n.toFixed(3)));
  return n.toExponential(1);
};

/**
 * Vertical bar chart. `bars` is [{label, value, colour, emphasis}].
 * A log value axis is used when the range spans more than two decades, which is the norm
 * here — linear bars would render every small category as invisible.
 */
function barChart(parent, bars, { height = 190, logScale = null } = {}) {
  const width = 430;
  const padding = { top: 12, right: 8, bottom: 46, left: 46 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const svg = el('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img' }, parent);
  const maximum = Math.max(...bars.map((b) => b.value), 1);
  const useLog = logScale === null ? maximum > 500 : logScale;
  const scale = (v) => {
    if (!useLog) return (v / maximum) * plotH;
    if (v <= 0) return 0;
    return (Math.log10(v + 1) / Math.log10(maximum + 1)) * plotH;
  };

  // gridlines
  const ticks = useLog
    ? Array.from({ length: Math.ceil(Math.log10(maximum + 1)) + 1 }, (_, i) => 10 ** i)
        .filter((v) => v <= maximum * 1.4)
    : [0, maximum / 2, maximum];
  for (const tick of ticks) {
    const y = padding.top + plotH - scale(tick);
    el('line', {
      x1: padding.left, x2: width - padding.right, y1: y, y2: y,
      stroke: COLOURS.grid, 'stroke-width': 1,
    }, svg);
    el('text', {
      x: padding.left - 6, y: y + 3.5, fill: COLOURS.ink,
      'font-size': 9.5, 'text-anchor': 'end',
    }, svg).textContent = shorten(Math.round(tick));
  }

  const slot = plotW / bars.length;
  const barWidth = Math.max(3, Math.min(slot - 4, 46));

  bars.forEach((bar, i) => {
    const h = scale(bar.value);
    const x = padding.left + i * slot + (slot - barWidth) / 2;
    const y = padding.top + plotH - h;
    el('rect', {
      x, y, width: barWidth, height: Math.max(h, bar.value > 0 ? 1.5 : 0),
      fill: bar.colour || COLOURS.bar, rx: 2,
      opacity: bar.emphasis ? 1 : 0.88,
      stroke: bar.emphasis ? '#fff' : 'none', 'stroke-width': bar.emphasis ? 1 : 0,
    }, svg).appendChild(
      el('title', {}, null),
    ).textContent = `${bar.label}: ${bar.value.toLocaleString()}`;

    if (bar.value > 0) {
      el('text', {
        x: x + barWidth / 2, y: y - 3.5, 'text-anchor': 'middle',
        class: 'bar-label',
      }, svg).textContent = shorten(bar.value);
    }

    const label = el('text', {
      x: x + barWidth / 2, y: padding.top + plotH + 12,
      'text-anchor': 'end', fill: COLOURS.ink, 'font-size': 9,
      transform: `rotate(-40 ${x + barWidth / 2} ${padding.top + plotH + 12})`,
    }, svg);
    label.textContent = bar.label;
  });

  el('line', {
    x1: padding.left, x2: width - padding.right,
    y1: padding.top + plotH, y2: padding.top + plotH,
    stroke: COLOURS.grid,
  }, svg);

  if (useLog) {
    el('text', {
      x: width - padding.right, y: 9, 'text-anchor': 'end',
      fill: COLOURS.ink, 'font-size': 9,
    }, svg).textContent = 'log scale';
  }
  return svg;
}

/** Scatter with log x (miss distance) and log y (Pc); censored drawn distinctly. */
function scatterMissVsPc(parent, events) {
  const width = 430;
  const height = 260;
  const padding = { top: 14, right: 12, bottom: 40, left: 52 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;
  const svg = el('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img' }, parent);

  const xMin = 0.005;
  const xMax = 70;
  const yMin = -10.5;
  const yMax = -3;
  const sx = (v) => padding.left + (Math.log10(Math.max(v, xMin)) - Math.log10(xMin))
    / (Math.log10(xMax) - Math.log10(xMin)) * plotW;
  const sy = (logv) => padding.top + plotH - ((logv - yMin) / (yMax - yMin)) * plotH;

  for (let d = -10; d <= -3; d++) {
    const y = sy(d);
    el('line', { x1: padding.left, x2: width - padding.right, y1: y, y2: y, stroke: COLOURS.grid }, svg);
    el('text', { x: padding.left - 6, y: y + 3.5, 'text-anchor': 'end', fill: COLOURS.ink, 'font-size': 9 }, svg)
      .textContent = `1e${d}`;
  }
  for (const x of [0.01, 0.1, 1, 10, 70]) {
    const px = sx(x);
    el('line', { x1: px, x2: px, y1: padding.top, y2: padding.top + plotH, stroke: COLOURS.grid }, svg);
    el('text', { x: px, y: padding.top + plotH + 13, 'text-anchor': 'middle', fill: COLOURS.ink, 'font-size': 9 }, svg)
      .textContent = `${x}`;
  }
  el('text', { x: padding.left + plotW / 2, y: height - 6, 'text-anchor': 'middle', fill: COLOURS.ink, 'font-size': 10 }, svg)
    .textContent = 'miss distance (km, log)';

  // the 1e-4 action threshold
  const thresholdY = sy(-4);
  el('line', {
    x1: padding.left, x2: width - padding.right, y1: thresholdY, y2: thresholdY,
    stroke: '#ff5c5c', 'stroke-width': 1.2, 'stroke-dasharray': '5 3', opacity: 0.85,
  }, svg);
  el('text', { x: width - padding.right, y: thresholdY - 4, 'text-anchor': 'end', fill: '#ff8a8a', 'font-size': 9 }, svg)
    .textContent = '1e-4 action threshold';

  // censored band, drawn as its own zone rather than as points on the Pc axis
  const censoredY = sy(-10.35);
  el('rect', {
    x: padding.left, y: censoredY - 7, width: plotW, height: 14,
    fill: COLOURS.censored, opacity: 0.12,
  }, svg);
  el('text', { x: padding.left + 4, y: censoredY + 3, fill: COLOURS.censored, 'font-size': 8.5 }, svg)
    .textContent = 'censored — bound, not a value';

  for (const event of events) {
    const isNull = event.pc === null || event.pc === undefined;
    if (isNull) continue;
    const censored = event.pc_is_floored;
    const y = censored ? censoredY + (Math.random() - 0.5) * 8 : sy(Math.log10(event.pc));
    el('circle', {
      cx: sx(event.miss_distance_km), cy: y, r: censored ? 1.5 : 2.1,
      fill: censored ? COLOURS.censored : (event.dilution === 1 ? COLOURS.diluted : COLOURS.robust),
      opacity: censored ? 0.5 : 0.75,
    }, svg);
  }
  return svg;
}

function legendRow(parent, items) {
  const div = document.createElement('div');
  div.style.cssText = 'display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 10px;font-size:11px;color:#98a0b8';
  div.innerHTML = items.map(([colour, label]) =>
    `<span style="display:flex;align-items:center;gap:5px">
       <span style="width:10px;height:10px;border-radius:2px;background:${colour};display:inline-block"></span>${label}
     </span>`).join('');
  parent.appendChild(div);
}

// ---------------------------------------------------------------------------------------

export function renderCharts(container, summary, events) {
  container.innerHTML = '';
  const population = summary.population;
  const bySource = population.by_source;

  // --- 1. Pc by decade, censored as a separate bar -------------------------------------
  {
    const wrap = card(container, 'Collision probability by decade', 'population',
      'Censored records are shown as their own bar, deliberately separated from the ' +
      'histogram — they sit at the 1e-10 floor and are upper bounds, not measurements. ' +
      'The floor itself is inferred from the data, not documented in the Users Guide.');
    const decades = {};
    for (const source of Object.values(bySource)) {
      for (const [key, value] of Object.entries(source.uncensored_decades || {})) {
        decades[key] = (decades[key] || 0) + value;
      }
    }
    const bars = Object.keys(decades).sort().map((key) => ({
      label: key.split('..')[0].replace('1e', '1e'),
      value: decades[key],
      colour: COLOURS.bar,
    }));
    bars.unshift({ label: 'CENSORED', value: population.censored, colour: COLOURS.censored, emphasis: true });
    bars.push({ label: 'no Pc', value: population.pc_null, colour: COLOURS.nullPc, emphasis: true });
    legendRow(wrap, [[COLOURS.bar, 'uncensored Pc'], [COLOURS.censored, 'censored (bound)'], [COLOURS.nullPc, 'not computable']]);
    barChart(wrap, bars);
  }

  // --- 2. events above the action threshold --------------------------------------------
  {
    const wrap = card(container, 'Events at or above the 1e-4 action threshold', 'population',
      'This is the population a triage benchmark would actually operate on. It is ' +
      'vanishingly small, and almost all of it is flagged as having diluted (untrustworthy) ' +
      'covariance — which constrains every downstream experiment.');
    const bars = [];
    for (const [name, source] of Object.entries(bySource)) {
      const robust = source.pc_by_dilution?.robust?.above_action_threshold ?? 0;
      const diluted = source.pc_by_dilution?.diluted?.above_action_threshold ?? 0;
      bars.push({ label: `${name} robust`, value: robust, colour: COLOURS.robust, emphasis: true });
      bars.push({ label: `${name} diluted`, value: diluted, colour: COLOURS.diluted, emphasis: true });
    }
    legendRow(wrap, [[COLOURS.robust, 'robust covariance'], [COLOURS.diluted, 'diluted covariance']]);
    barChart(wrap, bars, { logScale: false });
  }

  // --- 3. dilution split ----------------------------------------------------------------
  {
    const wrap = card(container, 'Covariance quality (dilution flag)', 'population',
      'dilution = 1 means the covariance is diluted: Pc has passed its maximum on the ' +
      'Pc-versus-scale-factor curve, so a lower Pc reflects worse knowledge, not lower risk.');
    const bars = [];
    for (const [name, source] of Object.entries(bySource)) {
      const values = source.dilution_values || {};
      bars.push({ label: `${name} robust`, value: values['0.0'] || 0, colour: COLOURS.robust });
      bars.push({ label: `${name} diluted`, value: values['1.0'] || 0, colour: COLOURS.diluted });
      bars.push({ label: `${name} null`, value: values.NULL || 0, colour: COLOURS.nullPc });
    }
    barChart(wrap, bars);
  }

  // --- 4. altitude ----------------------------------------------------------------------
  {
    const wrap = card(container, 'Altitude of both objects', 'population',
      'Object slots (two per event), |r| − 6378.137 km. Relevant to the later drag work: ' +
      'atmospheric drag only meaningfully affects the low bands.');
    const bands = {};
    for (const source of Object.values(bySource)) {
      for (const [key, value] of Object.entries(source.altitude_bands || {})) {
        bands[key] = (bands[key] || 0) + value;
      }
    }
    barChart(wrap, Object.entries(bands).map(([label, value]) => ({
      label: label.replace(' km', '').replace(/\(.*\)/, '').trim(), value, colour: COLOURS.bar,
    })));
  }

  // --- 5/6/7. quartile summaries --------------------------------------------------------
  const quartileCharts = [
    ['miss_distance_km', 'Miss distance', 'km'],
    ['relative_speed_kms', 'Relative speed', 'km/s'],
    ['mahalanobis_distance', 'Mahalanobis distance', 'σ'],
  ];
  for (const [key, title, unit] of quartileCharts) {
    const wrap = card(container, `${title} — quartiles by answer key`, 'population',
      `Minimum, lower quartile, median, upper quartile and maximum, in ${unit}.`);
    const bars = [];
    for (const [name, source] of Object.entries(bySource)) {
      const stats = source[key] || {};
      for (const stat of ['min', 'q1', 'median', 'q3', 'max']) {
        bars.push({
          label: `${name.slice(0, 4)} ${stat}`,
          value: Number(stats[stat] ?? 0),
          colour: name === 'spherical' ? COLOURS.bar : '#7d6bd8',
          emphasis: stat === 'median',
        });
      }
    }
    legendRow(wrap, [[COLOURS.bar, 'spherical'], ['#7d6bd8', 'SFSH'], ['#ffffff', 'median outlined']]);
    barChart(wrap, bars, { logScale: true });
  }

  // --- 8. covariance magnitude ----------------------------------------------------------
  {
    const wrap = card(container, 'Position uncertainty magnitude by decade', 'population',
      'Covariance trace (c11+c22+c33, km²), an upper bound on the largest eigenvalue. ' +
      'The spread across many decades is why uncertainty cannot be shown on a linear scale.');
    const decades = {};
    for (const source of Object.values(bySource)) {
      for (const [key, value] of Object.entries(source.covariance_trace_decades || {})) {
        decades[key] = (decades[key] || 0) + value;
      }
    }
    const sorted = Object.keys(decades).sort(
      (a, b) => parseInt(a.slice(2), 10) - parseInt(b.slice(2), 10));
    barChart(wrap, sorted.map((key) => ({
      label: key.split('..')[0], value: decades[key], colour: COLOURS.bar,
    })));
  }

  // --- 9. scatter -----------------------------------------------------------------------
  {
    const wrap = card(container, 'Miss distance against Pc', 'sample',
      'Drawn from the 2,000 rendered events, so the density here is a property of the ' +
      'sampling design, not of the dataset. Censored events are placed in their own band ' +
      'at the foot of the chart rather than plotted at 1e-10, because that value is a bound.');
    legendRow(wrap, [[COLOURS.robust, 'robust covariance'], [COLOURS.diluted, 'diluted covariance'],
      [COLOURS.censored, 'censored (own band)']]);
    scatterMissVsPc(wrap, events);
  }

  // --- 10. sample composition -----------------------------------------------------------
  {
    const wrap = card(container, 'What the 3D view is actually showing', 'sample',
      'Composition of the rendered sample by Pc class. Compare against the population ' +
      'chart above: rare high-Pc events are deliberately over-sampled so they appear at all.');
    const classes = {};
    for (const event of events) {
      const key = event.stratum.split('|')[1];
      classes[key] = (classes[key] || 0) + 1;
    }
    const order = ['action', 'near_threshold', 'moderate', 'low', 'censored', 'null'];
    barChart(wrap, order.filter((k) => classes[k]).map((key) => ({
      label: key,
      value: classes[key],
      colour: key === 'censored' ? COLOURS.censored
        : key === 'null' ? COLOURS.nullPc
        : key === 'action' ? '#ff2f2f' : COLOURS.bar,
      emphasis: key === 'action',
    })), { logScale: false });
  }
}
