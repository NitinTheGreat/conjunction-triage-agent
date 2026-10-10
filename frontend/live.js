// Live calculations and recorded evaluation results. Static exploration works without an API.

const API_CANDIDATES = [...new Set([
  ...(location.protocol.startsWith('http') ? [location.origin] : []),
  'http://127.0.0.1:8000',
  'http://127.0.0.1:8077',
])];
const HEALTH_TIMEOUT_MS = 2500;
const REQUEST_TIMEOUT_MS = 30000;
const TRIAGE_TIMEOUT_MS = 180000;
const $ = (id) => document.getElementById(id);

let apiBase = null;
let apiHealth = null;
let probing = false;
let pcBusy = false;
let exampleBusy = false;
let triageBusy = false;
let inputRevision = 0;

function revealOutput(id) {
  const output = $(id);
  // Preserve the reader's place if they switched workspaces while a request ran.
  if (output.closest('.view').hidden) return;
  output.tabIndex = -1;
  output.focus({ preventScroll: true });
  output.scrollIntoView({ block: 'start', behavior: 'instant' });
}

function markPreviousCalculation() {
  if (!$('pc-output').querySelector('.bignum') || $('pc-stale')) return;
  const notice = document.createElement('div');
  notice.id = 'pc-stale';
  notice.className = 'notice';
  notice.setAttribute('role', 'status');
  notice.textContent = 'Inputs changed. The result below uses the previous inputs; compute again to update it.';
  $('pc-output').prepend(notice);
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function parseNumbers(text, expected, label) {
  const parts = String(text).split(',').map((part) => part.trim());
  if (parts.length !== expected || parts.some((part) => part === '')) {
    throw new Error(`${label}: enter ${expected} comma-separated numbers.`);
  }
  return parts.map((part) => {
    const value = Number(part);
    if (!Number.isFinite(value)) throw new Error(`${label}: “${part}” is not a number.`);
    return value;
  });
}

function formatPc(pc) {
  if (pc === 0) return '0';
  if (!Number.isFinite(pc) || pc < 0) return 'Unavailable';
  const exponent = Math.floor(Math.log10(pc));
  const mantissa = pc / 10 ** exponent;
  return `${mantissa.toFixed(3)}<span class="exp"> × 10<sup>${exponent}</sup></span>`;
}

function percent(pc) {
  const value = pc * 100;
  if (value === 0) return '0%';
  return `${value < 0.0001 ? value.toExponential(3) : Number(value.toPrecision(4))}%`;
}

function showError(container, message, hint) {
  container.innerHTML = `<div class="error-box" role="alert"><strong>${escapeHtml(message)}</strong>${
    hint ? `<p>${escapeHtml(hint)}</p>` : ''
  }</div>`;
  if (container.id === 'pc-output' || container.id === 'triage-output') revealOutput(container.id);
}

async function fetchJson(url, options = {}, timeout = REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = typeof payload?.detail === 'string' ? payload.detail : `HTTP ${response.status}`;
      const error = new Error(detail);
      error.code = payload?.error;
      error.hint = payload?.hint;
      throw error;
    }
    if (!payload) throw new Error('The server did not return a JSON response.');
    return payload;
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error(`No response within ${timeout / 1000} seconds. The server may still be processing the request.`);
    }
    if (error instanceof TypeError) {
      throw new Error('The API connection was interrupted. Check the local server, then use Reconnect.');
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function callApi(path, body) {
  if (!apiBase) throw new Error('Connect to the local API first.');
  return fetchJson(`${apiBase}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, path === '/triage' ? TRIAGE_TIMEOUT_MS : REQUEST_TIMEOUT_MS);
}

function renderProvenance(provenance) {
  if (!provenance) return '';
  return `<details class="provenance">
    <summary>Method, source &amp; full response provenance</summary>
    <p>${escapeHtml(provenance.method || provenance.dataset || 'Recorded evaluation')}</p>
    ${provenance.dataset ? `<p><strong>Dataset:</strong> ${escapeHtml(provenance.dataset)}</p>` : ''}
    ${provenance.computed_at ? `<p>Computed ${escapeHtml(provenance.computed_at)} · code ${escapeHtml(provenance.code_version || 'unknown')}</p>` : ''}
    <p class="note">The original provenance is preserved below for inspection.</p>
    <pre>${escapeHtml(JSON.stringify(provenance, null, 2))}</pre>
  </details>`;
}

// Availability is checked per dependency: Pc needs only the API; benchmark imports need
// TraCSS; live triage needs both the selected Kelvins split and an LLM credential.
function availability() {
  const files = apiHealth?.checks?.kelvins_store?.files || [];
  const split = $('triage-split').value;
  const splitReady = apiHealth?.checks?.kelvins_store?.ok &&
    files.includes(`cdms_${split}.parquet`) && files.includes(`series_${split}.parquet`);
  return {
    pc: Boolean(apiBase),
    benchmark: Boolean(apiBase && apiHealth?.checks?.tracss_store?.ok &&
      apiHealth.checks.tracss_store.sources?.sfsh),
    triage: Boolean(apiBase && apiHealth?.checks?.llm?.ok && splitReady),
    splitReady,
  };
}

function updateAvailability() {
  const ready = availability();
  $('pc-submit').disabled = !ready.pc || pcBusy;
  $('pc-submit').textContent = pcBusy ? 'Computing…' : 'Compute probability';
  $('pc-example').disabled = !ready.benchmark || exampleBusy || pcBusy;
  $('pc-example').textContent = exampleBusy ? 'Loading dimensions…' : 'Use benchmark dimensions';
  if ($('pc-reset')) $('pc-reset').disabled = pcBusy || exampleBusy;
  $('triage-submit').disabled = !ready.triage || triageBusy;
  $('triage-submit').textContent = triageBusy ? 'Analysing series…' : 'Run live analysis';
  if ($('triage-example')) $('triage-example').disabled = triageBusy;
  if ($('api-retry')) {
    $('api-retry').disabled = probing;
    $('api-retry').textContent = probing ? 'Checking…' : 'Reconnect';
  }
  const pcStatus = !apiBase
    ? 'Start the local API to calculate. You can explore the inputs while disconnected.'
    : ready.benchmark
      ? 'Live physics is ready. Calculate with the example inputs or enter your own values.'
      : 'Live physics is ready. Benchmark dimensions are unavailable because the TraCSS store is missing.';
  const triageStatus = !apiBase
    ? 'Live analysis needs the local API. The recorded example and evaluation remain available.'
    : !ready.splitReady
      ? `Live analysis needs the ${$('triage-split').value} Kelvins dataset. The recorded example remains available.`
      : !apiHealth.checks.llm?.ok
        ? 'Live analysis needs an LLM API key configured on the server. The recorded example remains available.'
        : 'Live analysis is ready. In-scope series can use a provider call; existing cached responses may be reused.';
  if ($('pc-status')) $('pc-status').textContent = pcStatus;
  if ($('triage-status')) $('triage-status').textContent = triageStatus;
  $('pc-submit').title = ready.pc ? '' : pcStatus;
  $('pc-example').title = ready.benchmark ? 'Copies miss distance and object radii only.' : 'Requires the ingested SFSH benchmark.';
  $('triage-submit').title = ready.triage ? '' : triageStatus;
}

async function probe(base) {
  try {
    const health = await fetchJson(`${base}/health`, {}, HEALTH_TIMEOUT_MS);
    return health?.checks?.sgp4 && health?.checks?.tracss_store ? { base, health } : null;
  } catch {
    return null;
  }
}

async function discoverApi() {
  if (probing) return;
  probing = true;
  $('api-strip').className = 'api-strip probing';
  $('api-strip-text').textContent = 'Checking live services…';
  updateAvailability();
  const candidates = await Promise.all(API_CANDIDATES.map(probe));
  const found = candidates.find(Boolean);
  apiBase = found?.base || null;
  apiHealth = found?.health || null;
  const ready = availability();
  $('api-strip').className = `api-strip ${apiBase ? 'online' : 'offline'}`;
  $('api-strip-text').textContent = apiBase
    ? `Physics connected · ${ready.triage ? 'Live agent ready' : 'Recorded agent example available'}`
    : 'Static demo ready · Connect the API for live calculations';
  $('api-strip-text').title = apiBase ? `Connected to ${apiBase}` : '3D exploration, distributions, recorded triage and evaluation work without the API.';
  probing = false;
  updateAvailability();
}

// Probability calculator.
function readObject(prefix) {
  const name = `Object ${prefix.slice(1)}`;
  const position = parseNumbers($(`${prefix}-pos`).value, 3, `${name} position`);
  const velocity = parseNumbers($(`${prefix}-vel`).value, 3, `${name} velocity`);
  const diagonal = parseNumbers($(`${prefix}-cov`).value, 3, `${name} covariance`);
  if (diagonal.some((value) => value <= 0)) throw new Error(`${name}: covariance variances must be positive.`);
  const hbr = Number($(`${prefix}-hbr`).value);
  if (!Number.isFinite(hbr) || hbr <= 0 || hbr > 1000) {
    throw new Error(`${name}: hard-body radius must be greater than 0 and at most 1,000 metres.`);
  }
  return {
    position_km: position,
    velocity_kms: velocity,
    covariance: diagonal.map((value, i) => diagonal.map((_, j) => i === j ? value : 0)),
    hard_body_radius_m: hbr,
  };
}

function conditioningRow(label, report) {
  if (!report) return '';
  return `<div class="kv"><dt>${escapeHtml(label)}</dt><dd>${report.was_conditioned ? 'Repaired' : 'No repair'} · condition number ${Number(report.condition_number).toExponential(2)}</dd></div>`;
}

function renderPc(result) {
  const repaired = result.conditioning_2d.was_conditioned || result.conditioning_3d.was_conditioned;
  const frame = result.provenance?.covariance_frame === 'uvw' ? 'each object’s local UVW frame' : 'the shared ECI frame';
  $('pc-output').innerHTML = `
    <div class="result-card">
      <div class="section-label">Live physics result</div>
      <h3>Estimated collision probability</h3>
      <div class="bignum">${formatPc(result.pc)}</div>
      <p class="explain">${percent(result.pc)} under the supplied geometry, object sizes and position uncertainties.</p>
      <p class="note">This models one short encounter. It does not establish whether a collision will occur.</p>
      <div class="kv"><dt>Risk on the log scale</dt><dd>log<sub>10</sub> P<sub>c</sub> = ${result.log10_pc === null ? '−∞' : result.log10_pc.toFixed(4)}</dd></div>
      ${result.pc < 1e-10 ? '<div class="notice">Below the inferred TraCSS reporting floor of 10<sup>−10</sup>. A benchmark value at that floor is treated as an upper bound, rather than an exact probability.</div>' : ''}
    </div>
    <div class="result-card">
      <h3>What shaped this estimate</h3>
      <div class="kv"><dt>Miss distance</dt><dd>${result.miss_distance_km.toFixed(6)} km</dd></div>
      <p class="note">Separation of the two supplied positions at closest approach.</p>
      <div class="kv"><dt>Relative speed</dt><dd>${result.relative_speed_kms.toFixed(4)} km/s</dd></div>
      <div class="kv"><dt>Combined object radius</dt><dd>${result.combined_hard_body_radius_m} m</dd></div>
      <p class="note">The two hard-body radii are added to define the collision region.</p>
      <div class="kv"><dt>Covariance frame</dt><dd>${escapeHtml(frame)}</dd></div>
      <details>
        <summary>Uncertainty distance &amp; encounter plane</summary>
        <p>Mahalanobis distance measures separation relative to position uncertainty. The encounter plane is perpendicular to relative motion; the probability integral is evaluated there.</p>
        <div class="kv"><dt>Mahalanobis distance · 3D</dt><dd>${result.mahalanobis_distance_3d.toFixed(4)}</dd></div>
        <div class="kv"><dt>Mahalanobis distance · encounter plane</dt><dd>${result.mahalanobis_distance_2d.toFixed(4)}</dd></div>
        <p class="note">Projected position covariance (km²)</p>
        <pre>${escapeHtml(JSON.stringify(result.projected_covariance_km2, null, 2))}</pre>
      </details>
    </div>
    <div class="result-card">
      <h3>Covariance quality</h3>
      <p class="explain">${repaired ? 'A covariance repair was needed. Interpret this estimate with that adjustment in mind.' : 'No covariance repair was needed for this calculation.'}</p>
      ${conditioningRow('Combined 3 × 3 matrix', result.conditioning_3d)}
      ${conditioningRow('Projected 2 × 2 matrix', result.conditioning_2d)}
      <details>
        <summary>What does conditioning mean?</summary>
        <p>The calculation needs invertible, positive-definite covariance matrices. Very small eigenvalues may be raised to a numerical floor. The condition number describes how unevenly uncertainty is spread across directions; it does not verify the quality of the underlying observations.</p>
        <pre>${escapeHtml(JSON.stringify({ combined: result.conditioning_3d, projected: result.conditioning_2d }, null, 2))}</pre>
      </details>
      <p class="note">Method check: 11,059 uncensored comparisons from 20,000 sampled benchmark rows agreed within 0.1%. This checks numerical reproduction, not collision outcomes.</p>
      ${renderProvenance(result.provenance)}
    </div>`;
}

async function loadBenchmarkExample() {
  if (!availability().benchmark || exampleBusy) return;
  exampleBusy = true;
  updateAvailability();
  try {
    const payload = await fetchJson(`${apiBase}/events?source=sfsh&limit=1&exclude_floored=true&order_by=pc_desc`);
    if (!payload.events?.length) throw new Error('No benchmark rows were returned.');
    const event = payload.events[0];
    if (!Number.isFinite(event.miss_distance_km) || !Number.isFinite(event.object1_hbr_m) ||
        !Number.isFinite(event.object2_hbr_m)) throw new Error('This benchmark row is missing object radii or miss distance.');
    $('o1-hbr').value = event.object1_hbr_m;
    $('o2-hbr').value = event.object2_hbr_m;
    $('o1-pos').value = '7000, 0, 0';
    $('o2-pos').value = `7000, 0, ${event.miss_distance_km}`;
    $('pc-output').innerHTML = `<div class="result-card">
      <span class="badge">Partial benchmark example</span>
      <h3>Object sizes &amp; separation loaded</h3>
      <p>Only the hard-body radii and miss distance come from this benchmark row. Positions were arranged to reproduce that separation; velocities and covariance inputs remain as entered.</p>
      <div class="notice">The full original state is not available from this endpoint. Computing now gives an illustrative scenario, not a reproduction of this event’s published P<sub>c</sub>.</div>
      <details open>
        <summary>Published row for reference</summary>
        <div class="kv"><dt>Event ID</dt><dd>${escapeHtml(event.event_id)}</dd></div>
        <div class="kv"><dt>Published probability</dt><dd>${event.pc === null ? 'Unavailable' : formatPc(event.pc)}</dd></div>
        <div class="kv"><dt>Miss distance</dt><dd>${event.miss_distance_km.toFixed(6)} km</dd></div>
        <div class="kv"><dt>Published relative speed · not copied</dt><dd>${event.relative_speed_kms.toFixed(3)} km/s</dd></div>
        <div class="kv"><dt>Hard-body radii</dt><dd>${event.object1_hbr_m} m + ${event.object2_hbr_m} m</dd></div>
      </details>
      ${renderProvenance(payload.provenance)}
    </div>`;
  } catch (error) {
    showError($('pc-output'), 'Could not load benchmark dimensions.', error.message);
  } finally {
    exampleBusy = false;
    updateAvailability();
    revealOutput('pc-output');
  }
}

function wirePcCalculator() {
  $('pc-form').addEventListener('input', () => {
    inputRevision++;
    markPreviousCalculation();
  });
  $('pc-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!availability().pc || pcBusy) return;
    let body;
    try {
      body = { object1: readObject('o1'), object2: readObject('o2'), covariance_frame: $('pc-frame').value };
    } catch (error) {
      showError($('pc-output'), 'Check the inputs.', error.message);
      revealOutput('pc-output');
      return;
    }
    const submittedRevision = inputRevision;
    pcBusy = true;
    updateAvailability();
    $('pc-output').setAttribute('aria-busy', 'true');
    $('pc-output').innerHTML = '<div class="result-card"><p class="spinner">Calculating probability and checking covariance quality…</p></div>';
    try {
      renderPc(await callApi('/pc', body));
      if (submittedRevision !== inputRevision) markPreviousCalculation();
    } catch (error) {
      showError($('pc-output'), error.code === 'pc_undefined' ? 'Probability is undefined for these inputs.' : 'Calculation could not complete.', `${error.message}${error.hint ? ` ${error.hint}` : ''}`);
    } finally {
      pcBusy = false;
      $('pc-output').setAttribute('aria-busy', 'false');
      updateAvailability();
      revealOutput('pc-output');
    }
  });
  $('pc-example').addEventListener('click', loadBenchmarkExample);
  $('pc-reset')?.addEventListener('click', () => {
    $('pc-form').reset();
    $('pc-output').innerHTML = '<div class="result-card empty-state"><span class="section-label">Ready to calculate</span><h3>Illustrative inputs restored</h3><p>Compute the probability, then switch the covariance frame to see why its meaning matters.</p></div>';
  });
}

// Triage compares estimates of final calculated risk, not observed collision outcomes.
function riskValue(risk) {
  if (!Number.isFinite(risk)) return 'Unavailable';
  if (risk <= -30) return '<div class="val">−30.000</div><div class="note">Negligible-risk floor · not an exact probability</div>';
  return `<div class="val">${risk.toFixed(3)}</div><div class="note">P<sub>c</sub> ≈ ${formatPc(10 ** risk)}</div>`;
}

function renderVerdicts(payload, recorded = false) {
  const parts = payload.verdicts.map((verdict) => {
    if (verdict.error) {
      return `<div class="verdict"><h4>${escapeHtml(verdict.series_id)}</h4><div class="error-box">${escapeHtml(verdict.error)}</div></div>`;
    }
    const baseline = `<div class="baseline"><div class="who">Latest visible CDM · baseline</div>${riskValue(verdict.baseline_risk)}</div>`;
    if (!verdict.in_scope) {
      return `<div class="verdict"><h4>${escapeHtml(verdict.series_id)} <span class="badge">Baseline retained</span></h4>
        <div class="pair">${baseline}<div class="agent"><div class="who">Agent estimate</div><div class="val">Not invoked</div></div></div>
        <p class="reasoning">The latest visible risk is below the −7 alert threshold. The workflow keeps the baseline and makes no LLM call for this series.</p></div>`;
    }
    const moved = verdict.predicted_final_risk - verdict.baseline_risk;
    const direction = Math.abs(moved) < 0.005 ? 'kept the baseline estimate' : `shifted log-risk ${moved > 0 ? 'up' : 'down'} by ${Math.abs(moved).toFixed(2)}`;
    const cites = (verdict.evidence_cited || []).map((cite) => `<li><code>${escapeHtml(cite.field)}</code>: ${escapeHtml(typeof cite.value === 'object' ? JSON.stringify(cite.value) : cite.value)}</li>`).join('');
    return `<div class="verdict">
      <h4>${escapeHtml(verdict.series_id)} <span class="badge">${recorded ? 'Recorded' : 'API response'}</span></h4>
      <div class="pair">${baseline}<div class="agent"><div class="who">Agent estimate</div>${riskValue(verdict.predicted_final_risk)}</div></div>
      <p class="explain">The agent ${direction}. Its classification: ${verdict.will_collapse ? 'risk resolves to negligible' : 'elevated risk persists'}.</p>
      <p class="note">Confidence: ${escapeHtml(verdict.confidence || 'not supplied')} (the model’s self-report, not a calibrated probability).</p>
      <details open><summary>Agent’s explanation</summary><p class="note">Original model reasoning; its physical claims are not independently verified here.</p><p class="reasoning">${escapeHtml(verdict.reasoning || 'No explanation supplied.')}</p></details>
      ${cites ? `<details><summary>Fields cited by the agent</summary><ul class="cites">${cites}</ul></details>` : ''}
    </div>`;
  }).join('');
  $('triage-output').innerHTML = `<div class="result-card">
    <div class="section-label">${recorded ? 'Recorded demonstration · no provider call' : 'Live API response'}</div>
    <h3>${payload.answered} answered · ${payload.failed} failed</h3>
    <p class="note">${payload.requested} requested. Values are log<sub>10</sub>(P<sub>c</sub>): −5 means 0.001%; −7 means 0.00001%. More negative means a smaller estimated probability.</p>
    ${recorded ? '<div class="notice">This saved response demonstrates the original evaluation workflow. It is not a new prediction, and its series may differ from the IDs entered in the live form.</div>' : ''}
    ${parts}
    <div class="insight">In the frozen test evaluation, the latest-CDM baseline scored better overall. An individual explanation does not establish that the agent’s correction is accurate.</div>
    ${renderProvenance(payload.provenance)}
  </div>`;
}

function wireTriage() {
  $('triage-split').addEventListener('change', updateAvailability);
  $('triage-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!availability().triage || triageBusy) return;
    const ids = $('triage-ids').value.split(',').map((id) => id.trim()).filter(Boolean);
    const split = $('triage-split').value;
    if (!ids.length || ids.length > 10) {
      showError($('triage-output'), 'Enter between 1 and 10 series IDs.', 'Separate IDs with commas; for example: test:100, test:1001.');
      return;
    }
    if (new Set(ids).size !== ids.length) {
      showError($('triage-output'), 'A series ID is repeated.', 'Remove duplicate IDs before running the analysis.');
      return;
    }
    if (ids.some((id) => !new RegExp(`^${split}:\\d+$`).test(id))) {
      showError($('triage-output'), 'The IDs must match the selected dataset split.', `Use IDs such as ${split}:100 with the “${split}” split.`);
      return;
    }
    triageBusy = true;
    updateAvailability();
    $('triage-output').setAttribute('aria-busy', 'true');
    $('triage-output').innerHTML = `<div class="result-card"><p class="spinner">Analysing ${ids.length} series. In-scope events may call the model or reuse a cached response. This can take a few minutes.</p></div>`;
    try {
      renderVerdicts(await callApi('/triage', { series_ids: ids, split }));
    } catch (error) {
      showError($('triage-output'), error.code === 'llm_unavailable' ? 'No LLM credential configured.' : 'Analysis could not complete.', `${error.message}${error.hint ? ` ${error.hint}` : ''}`);
    } finally {
      triageBusy = false;
      $('triage-output').setAttribute('aria-busy', 'false');
      updateAvailability();
      revealOutput('triage-output');
    }
  });
  $('triage-example')?.addEventListener('click', async () => {
    if (triageBusy) return;
    const button = $('triage-example');
    button.disabled = true;
    try {
      renderVerdicts(await fetchJson('./data/triage_example.json'), true);
      revealOutput('triage-output');
    } catch (error) {
      showError($('triage-output'), 'The recorded example could not load.', error.message);
    } finally {
      button.disabled = false;
    }
  });
}

// The evaluation tab reads the frozen export and works independently of all live services.
function renderResults(data) {
  const rows = data.arms.map((arm) => `<tr class="${arm.is_baseline ? 'baseline' : arm.is_agent ? 'agent' : ''}">
    <td><strong>${escapeHtml(arm.label)}</strong><span class="desc">${escapeHtml(arm.description)}</span></td>
    <td><strong>${arm.L.toFixed(4)}</strong></td>
    <td>${arm.mse_hr === null ? '—' : arm.mse_hr.toFixed(4)}</td>
    <td>${arm.f2 === null ? '—' : arm.f2.toFixed(4)}</td>
    <td>${arm.precision === null ? '—' : `${(arm.precision * 100).toFixed(1)}%`}</td>
    <td>${arm.recall === null ? '—' : `${(arm.recall * 100).toFixed(1)}%`}</td>
  </tr>`).join('');
  const comparison = data.agent_vs_b1;
  const baseline = data.arms.find((arm) => arm.is_baseline);
  const agent = data.arms.find((arm) => arm.is_agent);
  const leaderboardNames = {
    CRP_baseline_constant_minus5: 'Constant −5 baseline (CRP)',
    LRP_baseline_latest_risk: 'Latest-risk baseline (LRP)',
    winner_sesc: 'Competition winner · sesc',
    tenth_spacemeister: '10th place · spacemeister',
  };
  const leaderboard = Object.entries(data.published_leaderboard || {}).map(([name, value]) => `<tr>
    <td>${escapeHtml(leaderboardNames[name] || name)}</td>
    <td>${typeof value === 'number' ? value.toFixed(3) : value.L.toFixed(3)}</td>
    <td>${value.mse_hr == null ? '—' : value.mse_hr.toFixed(3)}</td>
    <td>${value.f2 == null ? '—' : value.f2.toFixed(3)}</td>
  </tr>`).join('');
  $('results-output').innerHTML = `
    <div class="headline-box">
      <div class="section-label">Main finding · frozen Phase 7 evaluation</div>
      <div class="big">The latest-risk baseline performed better.</div>
      <p>${escapeHtml(data.headline)} The result supports retaining the baseline for this benchmark comparison.</p>
    </div>
    <div class="metric-grid">
      <div class="metric-card baseline"><span class="section-label">Latest-CDM baseline</span><div class="bignum">${baseline.L.toFixed(4)}</div><p>Loss L · lower is better</p></div>
      <div class="metric-card agent"><span class="section-label">LLM agent · prompt v1</span><div class="bignum">${agent.L.toFixed(4)}</div><p>${(agent.L / baseline.L).toFixed(2)} × the baseline loss</p></div>
      <div class="metric-card"><span class="section-label">Test events</span><div class="bignum">${data.test_events.toLocaleString()}</div><p>${data.test_high_risk} with high-risk final labels (${data.test_high_risk_pct}%)</p></div>
    </div>
    <div class="result-card">
      <h3>How to read the score</h3>
      <p><strong>L = MSE<sub>HR</sub> / F<sub>2</sub>.</strong> It combines numerical prediction error with the ability to identify high-risk labels. A smaller L is better.</p>
      <details><summary>Metric definitions</summary>
        <dl>
          <div class="kv"><dt>MSE<sub>HR</sub> · lower is better</dt><dd>Mean squared error in predicted log-risk, evaluated on events with high-risk final labels. The challenge replaces low-risk predictions with −6.001 before scoring.</dd></div>
          <div class="kv"><dt>F<sub>2</sub> · higher is better</dt><dd>Precision and recall combined, weighting recall more heavily (β = 2).</dd></div>
          <div class="kv"><dt>Precision</dt><dd>Of predicted high-risk events, the fraction whose final labels are high-risk.</dd></div>
          <div class="kv"><dt>Recall</dt><dd>Of events with high-risk final labels, the fraction correctly flagged.</dd></div>
        </dl>
        <p class="note">“High-risk” follows the benchmark’s log-risk threshold of −6 (P<sub>c</sub> = 10<sup>−6</sup>). These are final calculated probability labels, not observed collisions. The agent’s broader invocation threshold is −7.</p>
      </details>
    </div>
    <div class="result-card">
      <h3>All six evaluated approaches</h3>
      <p class="note">Scores from the frozen held-out evaluation. Baseline and agent rows are labelled and highlighted.</p>
      <div class="table-scroll" tabindex="0" role="region" aria-label="All six approaches: horizontally scrollable evaluation table">
        <table class="results"><thead><tr><th scope="col">Approach</th><th scope="col">Loss L ↓</th><th scope="col">MSE<sub>HR</sub> ↓</th><th scope="col">F<sub>2</sub> ↑</th><th scope="col">Precision ↑</th><th scope="col">Recall ↑</th></tr></thead><tbody>${rows}</tbody></table>
      </div>
    </div>
    <div class="result-card">
      <h3>How consistent was the difference?</h3>
      <p>The paired bootstrap repeatedly resamples the same test events. A positive loss difference favours the baseline.</p>
      <div class="kv"><dt>Median loss difference · agent minus baseline</dt><dd>+${comparison.median_difference.toFixed(4)}</dd></div>
      <div class="kv"><dt>95% bootstrap interval</dt><dd>[+${comparison.ci_low.toFixed(4)}, +${comparison.ci_high.toFixed(4)}]</dd></div>
      <div class="kv"><dt>Resamples favouring the agent</dt><dd>${(100 * comparison.fraction_favouring_agent).toFixed(1)}% of ${comparison.resamples.toLocaleString()}</dd></div>
      <p class="note">${escapeHtml(comparison.note)}</p>
    </div>
    <div class="result-card">
      <h3>Published 2019 challenge comparison</h3>
      <div class="table-scroll" tabindex="0" role="region" aria-label="Published challenge scores">
        <table class="results"><thead><tr><th scope="col">Published approach</th><th scope="col">Loss L ↓</th><th scope="col">MSE<sub>HR</sub> ↓</th><th scope="col">F<sub>2</sub> ↑</th></tr></thead><tbody>${leaderboard}</tbody></table>
      </div>
      <p class="note">Source: <a href="https://arxiv.org/abs/2008.03069" target="_blank" rel="noopener noreferrer">${escapeHtml(data.published_source)}</a>. The local latest-risk baseline matches the published LRP to four decimal places; the constant −5 arm matches CRP to three significant figures.</p>
    </div>
    <div class="result-card">
      <details><summary>Evaluation provenance &amp; frozen manifest</summary>
        <p>${escapeHtml(data.provenance)}</p>
        <p>Manifest commit <code>${escapeHtml(data.frozen_manifest_head || '')}</code>, committed before the test set was scored.</p>
        <p class="note">This page reports the original frozen evaluation. It does not recompute scores when live inputs, code or prompts change.</p>
      </details>
    </div>`;
}

async function loadResults() {
  try {
    renderResults(await fetchJson('./data/phase7_results.json'));
  } catch (error) {
    showError($('results-output'), 'Could not load the evaluation export.', `${error.message} Restore frontend/data/phase7_results.json or regenerate it with python scripts/export_frontend_data.py.`);
  }
}

wirePcCalculator();
wireTriage();
$('api-retry')?.addEventListener('click', discoverApi);
loadResults();
discoverApi();
