/**
 * Distribution charts, drawn as hand-built SVG. No charting library, no CDN.
 *
 * Every chart declares its scope — POPULATION (all ingested records, via
 * summary.json) or SAMPLE (the stratified records actually rendered in 3D). The two
 * are never mixed inside one chart, because the sample deliberately over-represents rare
 * high-probability events and reading a dataset proportion off it would be wrong.
 *
 * Censored Pc is always drawn as a separate labelled bar, never merged into the
 * histogram: it is a bound at the 1e-10 floor, not a measurement.
 */

const NS = 'http://www.w3.org/2000/svg';
let chartId = 0;

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

function card(container, title, scope, note, counts) {
  const wrap = document.createElement('section');
  wrap.className = 'card';
  const heading = document.createElement('h3');
  heading.id = `chart-heading-${++chartId}`;
  heading.textContent = title;
  wrap.setAttribute('aria-labelledby', heading.id);
  wrap.appendChild(heading);
  const badge = document.createElement('span');
  badge.className = `scope ${scope}`;
  badge.textContent = scope === 'population'
    ? `Full dataset · ${counts.population.toLocaleString()} ingested records`
    : `3D sample · ${counts.sample.toLocaleString()} records`;
  wrap.appendChild(badge);
  if (note) {
    const explanation = document.createElement('p');
    explanation.className = 'note';
    explanation.textContent = note;
    wrap.appendChild(explanation);
  }
  container.appendChild(wrap);
  return wrap;
}

function describeChart(svg, parent, description) {
  const titleId = `chart-title-${++chartId}`;
  const descriptionId = `chart-description-${chartId}`;
  svg.setAttribute('aria-labelledby', titleId);
  svg.setAttribute('aria-describedby', descriptionId);
  el('title', { id: titleId }, svg).textContent = parent.querySelector('h3').textContent;
  el('desc', { id: descriptionId }, svg).textContent = description;
}

const exact = (value) => Number.isInteger(value) ? value.toLocaleString('en-US') : String(value);
const sourceLabel = (name) => name === 'spherical' ? 'Sph.' : name.toUpperCase();

/** Compact bar label. Values here span counts in the millions and physical quantities
 *  below 0.01, so both ends need trimming or the labels collide with the axis. */
const shorten = (n) => {
  if (n === 0) return '0';
  const a = Math.abs(n);
  if (a >= 1e6) return `${(n / 1e6).toFixed(a >= 1e7 ? 0 : 1)}M`;
  if (a >= 1e3) return `${(n / 1e3).toFixed(a >= 1e4 ? 0 : 1)}k`;
  if (a >= 1) return String(Number(n.toFixed(2)));
  if (a >= 0.01) return String(Number(n.toFixed(3)));
  return n.toExponential(1);
};

/**
 * Vertical bar chart. `bars` is [{label, value, colour, emphasis}].
 * A log(1 + value) axis keeps small categories visible alongside very large values.
 * Tick labels always show the original quantity, and exact values are available below.
 */
function barChart(parent, bars, { height = 240, logScale = null, unit = 'records' } = {}) {
  const width = 480;
  const padding = { top: 24, right: 10, bottom: 64, left: 54 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const svg = el('svg', { viewBox: `0 0 ${width} ${height}`, role: 'group' }, parent);
  const maximum = Math.max(...bars.map((b) => b.value), 1);
  const useLog = logScale === null ? maximum > 500 : logScale;
  const scale = (v) => {
    if (!useLog) return (v / maximum) * plotH;
    if (v <= 0) return 0;
    return (Math.log10(v + 1) / Math.log10(maximum + 1)) * plotH;
  };

  describeChart(svg, parent,
    `Bar chart in ${unit}. ${useLog ? 'Heights use log base 10 of one plus the value; axis labels show original values.' : 'Heights use a linear scale.'} ` +
    'Focus a bar to read its value, or expand the exact values table below.');
  const readout = document.createElement('p');
  readout.className = 'chart-readout';
  readout.setAttribute('role', 'status');
  readout.setAttribute('aria-live', 'polite');
  readout.textContent = 'Hover or focus a bar to inspect its value.';

  // Gridlines are in the original units, including a zero baseline.
  const candidateTicks = useLog
    ? [0, ...Array.from({ length: Math.ceil(Math.log10(maximum + 1)) + 1 }, (_, i) => 10 ** i)
        .filter((v) => v <= maximum)]
    : [0, maximum / 2, maximum];
  const ticks = candidateTicks.filter((tick, index) =>
    index === 0 || scale(tick) - scale(candidateTicks[index - 1]) >= 12);
  for (const tick of ticks) {
    const y = padding.top + plotH - scale(tick);
    el('line', {
      x1: padding.left, x2: width - padding.right, y1: y, y2: y,
      stroke: COLOURS.grid, 'stroke-width': 1,
    }, svg);
    el('text', {
      x: padding.left - 6, y: y + 3.5, fill: COLOURS.ink,
      'font-size': 9.5, 'text-anchor': 'end',
    }, svg).textContent = shorten(tick);
  }

  const slot = plotW / bars.length;
  const barWidth = Math.max(3, Math.min(slot - 4, 46));

  bars.forEach((bar, i) => {
    const h = scale(bar.value);
    const x = padding.left + i * slot + (slot - barWidth) / 2;
    const y = padding.top + plotH - h;
    const valueLabel = `${bar.label}: ${exact(bar.value)} ${unit}`;
    const rectangle = el('rect', {
      x, y, width: barWidth, height: Math.max(h, bar.value > 0 ? 1.5 : 0),
      fill: bar.colour || COLOURS.bar, rx: 2,
      opacity: bar.emphasis ? 1 : 0.88,
      stroke: bar.emphasis ? '#fff' : 'none', 'stroke-width': bar.emphasis ? 1 : 0,
      tabindex: 0, role: 'img', 'aria-label': valueLabel,
    }, svg);
    el('title', {}, rectangle).textContent = valueLabel;
    rectangle.addEventListener('mouseenter', () => { readout.textContent = valueLabel; });
    rectangle.addEventListener('focus', () => { readout.textContent = valueLabel; });

    if (bars.length <= 12) {
      el('text', {
        x: x + barWidth / 2, y: y - 3.5, 'text-anchor': 'middle',
        class: 'bar-label',
      }, svg).textContent = shorten(bar.value);
    }

    const label = el('text', {
      x: x + barWidth / 2, y: padding.top + plotH + 12,
      'text-anchor': 'end', fill: COLOURS.ink, 'font-size': 10,
      transform: `rotate(-40 ${x + barWidth / 2} ${padding.top + plotH + 12})`,
    }, svg);
    label.textContent = bar.label;
  });

  el('line', {
    x1: padding.left, x2: width - padding.right,
    y1: padding.top + plotH, y2: padding.top + plotH,
    stroke: COLOURS.grid,
  }, svg);

  el('text', {
    x: padding.left, y: 11, fill: COLOURS.ink, 'font-size': 10,
  }, svg).textContent = unit;
  el('text', {
    x: width - padding.right, y: 11, 'text-anchor': 'end',
    fill: COLOURS.ink, 'font-size': 9,
  }, svg).textContent = useLog ? 'Height: log₁₀(1 + value)' : 'Linear scale';
  parent.appendChild(readout);

  const disclosure = document.createElement('details');
  disclosure.className = 'chart-values';
  const summary = document.createElement('summary');
  summary.textContent = 'View exact values';
  disclosure.appendChild(summary);
  const table = document.createElement('table');
  const caption = document.createElement('caption');
  caption.textContent = `${parent.querySelector('h3').textContent} (${unit})`;
  table.appendChild(caption);
  const header = table.createTHead().insertRow();
  for (const label of ['Category', unit]) {
    const th = document.createElement('th');
    th.scope = 'col';
    th.textContent = label;
    header.appendChild(th);
  }
  const body = table.createTBody();
  for (const bar of bars) {
    const row = body.insertRow();
    const label = document.createElement('th');
    label.scope = 'row';
    label.textContent = bar.label;
    row.appendChild(label);
    row.insertCell().textContent = exact(bar.value);
  }
  disclosure.appendChild(table);
  parent.appendChild(disclosure);
  return svg;
}

/** Scatter with log x (miss distance) and log y (Pc); censored drawn distinctly. */
function scatterMissVsPc(parent, events) {
  const width = 480;
  const height = 290;
  const padding = { top: 25, right: 12, bottom: 40, left: 52 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;
  const svg = el('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img' }, parent);
  const missing = events.filter((event) => event.pc === null || event.pc === undefined).length;
  describeChart(svg, parent,
    `Scatter plot of miss distance and collision probability for ${events.length.toLocaleString()} sampled records. ` +
    'Both axes use logarithmic scales. Gray points occupy a separate censored band. ' +
    `${missing.toLocaleString()} records without a probability are omitted. ` +
    'This deliberately selected sample does not show the frequency of events in the full dataset.');

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
    .textContent = 'Miss distance · km · logarithmic scale';
  el('text', { x: padding.left, y: 11, fill: COLOURS.ink, 'font-size': 10 }, svg)
    .textContent = 'Collision probability (Pc)';

  // The dataset's 1e-4 reference threshold, distinct from the Kelvins benchmark threshold.
  const thresholdY = sy(-4);
  el('line', {
    x1: padding.left, x2: width - padding.right, y1: thresholdY, y2: thresholdY,
    stroke: '#ff5c5c', 'stroke-width': 1.2, 'stroke-dasharray': '5 3', opacity: 0.85,
  }, svg);
  el('text', { x: width - padding.right, y: thresholdY - 4, 'text-anchor': 'end', fill: '#ff8a8a', 'font-size': 9 }, svg)
    .textContent = '1e−4 reference threshold';

  // censored band, drawn as its own zone rather than as points on the Pc axis
  const censoredY = sy(-10.35);
  el('rect', {
    x: padding.left, y: censoredY - 7, width: plotW, height: 14,
    fill: COLOURS.censored, opacity: 0.12,
  }, svg);
  el('text', { x: padding.left + 4, y: censoredY + 3, fill: COLOURS.censored, 'font-size': 8.5 }, svg)
    .textContent = 'Censored: Pc at or below the inferred floor';

  for (const [index, event] of events.entries()) {
    const isNull = event.pc === null || event.pc === undefined;
    if (isNull) continue;
    const censored = event.pc_is_floored;
    // Deterministic separation in the censored band; vertical position is not a Pc value.
    const y = censored ? censoredY + (((index * 37) % 101) / 100 - 0.5) * 8 : sy(Math.log10(event.pc));
    const point = el('circle', {
      cx: sx(event.miss_distance_km), cy: y, r: censored ? 1.5 : 2.1,
      fill: censored ? COLOURS.censored : (event.dilution === 1 ? COLOURS.diluted
        : event.dilution === 0 ? COLOURS.robust : COLOURS.nullPc),
      opacity: censored ? 0.5 : 0.75,
    }, svg);
    el('title', {}, point).textContent =
      `Miss distance: ${exact(event.miss_distance_km)} km. ` +
      (censored ? 'Pc is censored at the inferred 1e−10 floor.' : `Pc: ${event.pc.toExponential(3)}.`);
  }
  const readout = document.createElement('p');
  readout.className = 'chart-readout';
  readout.textContent = `${missing.toLocaleString()} records have no Pc and are omitted. Point density reflects sample selection.`;
  parent.appendChild(readout);
  return svg;
}

function legendRow(parent, items) {
  const div = document.createElement('div');
  div.className = 'chart-legend';
  div.style.cssText = 'display:flex;flex-wrap:wrap;gap:10px;margin:6px 0 10px;font-size:12px;color:#98a0b8';
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
  const counts = {
    population: population.events ?? Object.values(bySource).reduce((total, source) => total + source.events, 0),
    sample: events.length,
  };
  const chart = (title, scope, note) => card(container, title, scope, note, counts);

  // --- 1. Pc by decade, censored as a separate bar -------------------------------------
  {
    const wrap = chart('How collision probabilities are distributed', 'population',
      'Blue bars group Pc into powers of ten; labels show the lower edge of each range. ' +
      'Gray records are at the inferred 1e−10 reporting floor: a bound, not an exact probability. ' +
      'This floor is inferred from the data, not documented by the provider.');
    const decades = {};
    for (const source of Object.values(bySource)) {
      for (const [key, value] of Object.entries(source.uncensored_decades || {})) {
        decades[key] = (decades[key] || 0) + value;
      }
    }
    const bars = Object.keys(decades).sort((a, b) => Number(a.split('..')[0]) - Number(b.split('..')[0])).map((key) => ({
      label: key.split('..')[0],
      value: decades[key],
      colour: COLOURS.bar,
    }));
    bars.unshift({ label: 'Censored', value: population.censored, colour: COLOURS.censored, emphasis: true });
    bars.push({ label: 'no Pc', value: population.pc_null, colour: COLOURS.nullPc, emphasis: true });
    legendRow(wrap, [[COLOURS.bar, 'Reported Pc above floor'], [COLOURS.censored, 'Censored bound'], [COLOURS.nullPc, 'No Pc reported']]);
    barChart(wrap, bars);
  }

  // --- 2. events above the action threshold --------------------------------------------
  {
    const wrap = chart('Records above the reference threshold', 'population',
      'Pc ≥ 1e−4 means at least 1 in 10,000 under the model. Compare records with and without ' +
      'a dilution flag before interpreting that probability. This is a reference level for ' +
      'this dataset; the separate Kelvins agent is invoked at latest Pc ≥ 1e−7.');
    const bars = [];
    for (const [name, source] of Object.entries(bySource)) {
      const robust = source.pc_by_dilution?.robust?.above_action_threshold ?? 0;
      const diluted = source.pc_by_dilution?.diluted?.above_action_threshold ?? 0;
      bars.push({ label: `${sourceLabel(name)} unflagged`, value: robust, colour: COLOURS.robust, emphasis: true });
      bars.push({ label: `${sourceLabel(name)} flagged`, value: diluted, colour: COLOURS.diluted, emphasis: true });
    }
    legendRow(wrap, [[COLOURS.robust, 'No dilution flag'], [COLOURS.diluted, 'Dilution flagged']]);
    barChart(wrap, bars, { logScale: false });
  }

  // --- 3. dilution split ----------------------------------------------------------------
  {
    const wrap = chart('When uncertainty can hide risk', 'population',
      'A dilution flag warns that broadening the position uncertainty can lower the calculated Pc. ' +
      'A small Pc can therefore coexist with poor knowledge of the orbit. An absent flag does ' +
      'not by itself verify the accuracy of the uncertainty estimate.');
    const bars = [];
    for (const [name, source] of Object.entries(bySource)) {
      const values = source.dilution_values || {};
      bars.push({ label: `${sourceLabel(name)} unflagged`, value: values['0.0'] || 0, colour: COLOURS.robust });
      bars.push({ label: `${sourceLabel(name)} flagged`, value: values['1.0'] || 0, colour: COLOURS.diluted });
      bars.push({ label: `${sourceLabel(name)} unknown`, value: values.NULL || 0, colour: COLOURS.nullPc });
    }
    barChart(wrap, bars);
  }

  // --- 4. altitude ----------------------------------------------------------------------
  {
    const wrap = chart('Where the objects are', 'population',
      'Altitude in kilometres above a spherical Earth (radius 6,378.137 km). Each record ' +
      'contributes two object observations, so these counts are not unique satellites. ' +
      'Lower orbits are more sensitive to atmospheric drag.');
    const bands = {};
    for (const source of Object.values(bySource)) {
      for (const [key, value] of Object.entries(source.altitude_bands || {})) {
        bands[key] = (bands[key] || 0) + value;
      }
    }
    barChart(wrap, Object.entries(bands).map(([label, value]) => ({
      label: label.replace(' km', '').replace(/\(.*\)/, '').trim(), value, colour: COLOURS.bar,
    })), { unit: 'object observations' });
  }

  // --- 5/6/7. quartile summaries --------------------------------------------------------
  const quartileCharts = [
    ['miss_distance_km', 'How close the objects pass', 'km', 'Miss distance is the predicted separation at closest approach.'],
    ['relative_speed_kms', 'How quickly the objects pass', 'km/s', 'Relative speed measures how fast one object moves past the other.'],
    ['mahalanobis_distance', 'Separation relative to uncertainty', 'dimensionless', 'Mahalanobis distance measures separation after accounting for position uncertainty.'],
  ];
  for (const [key, title, unit, definition] of quartileCharts) {
    const wrap = chart(title, 'population',
      `${definition} Each source shows its minimum, 25th percentile (Q1), median, ` +
      '75th percentile (Q3) and maximum. White outlines mark the medians.');
    const bars = [];
    for (const [name, source] of Object.entries(bySource)) {
      const stats = source[key] || {};
      for (const stat of ['min', 'q1', 'median', 'q3', 'max']) {
        bars.push({
          label: `${sourceLabel(name)} ${stat}`,
          value: Number(stats[stat] ?? 0),
          colour: name === 'spherical' ? COLOURS.bar : '#7d6bd8',
          emphasis: stat === 'median',
        });
      }
    }
    legendRow(wrap, [[COLOURS.bar, 'Spherical source'], ['#7d6bd8', 'SFSH source'], ['#ffffff', 'Median outlined']]);
    barChart(wrap, bars, { logScale: true, unit });
  }

  // --- 8. covariance magnitude ----------------------------------------------------------
  {
    const wrap = chart('How much position uncertainty varies', 'population',
      'The covariance trace adds the three position variances (c11 + c22 + c33), in km². ' +
      'For a valid covariance it bounds the largest eigenvalue. Each bar counts object ' +
      'observations within a power-of-ten range, labelled by its lower edge.');
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
    })), { unit: 'object observations' });
  }

  // --- 9. scatter -----------------------------------------------------------------------
  {
    const wrap = chart('A close pass does not tell the whole story', 'sample',
      'Compare predicted separation with Pc. Rare high-Pc records are deliberately over-represented, ' +
      'so dot density does not show their real prevalence. Gray points sit in a separate censored ' +
      'band because their exact probability is unknown.');
    legendRow(wrap, [[COLOURS.robust, 'No dilution flag'], [COLOURS.diluted, 'Dilution flagged'],
      [COLOURS.censored, 'Censored bound'], [COLOURS.nullPc, 'Dilution flag unknown']]);
    scatterMissVsPc(wrap, events);
  }

  // --- 10. sample composition -----------------------------------------------------------
  {
    const wrap = chart('What is included in the 3D sample', 'sample',
      'Records grouped by the sampling categories used for the 3D view. Compare with the first ' +
      'chart: rare high-Pc records are intentionally sampled more often so they remain visible. ' +
      'The lowest Pc range excludes censored records.');
    const classes = {};
    for (const event of events) {
      const key = event.stratum.split('|')[1];
      classes[key] = (classes[key] || 0) + 1;
    }
    const order = ['action', 'near_threshold', 'moderate', 'low', 'censored', 'null'];
    const labels = {
      action: '≥ 1e−4', near_threshold: '1e−6 to < 1e−4', moderate: '1e−8 to < 1e−6',
      low: '< 1e−8', censored: 'Censored', null: 'No Pc',
    };
    barChart(wrap, order.filter((k) => classes[k]).map((key) => ({
      label: labels[key],
      value: classes[key],
      colour: key === 'censored' ? COLOURS.censored
        : key === 'null' ? COLOURS.nullPc
        : key === 'action' ? '#ff2f2f' : COLOURS.bar,
      emphasis: key === 'action',
    })), { logScale: false });
  }
}
