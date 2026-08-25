// Phase 9 — the live half of the frontend.
//
// The Phase 3 tabs (3D geometry, Distributions) read a static JSON export and keep working
// with nothing running. The three tabs added here talk to the FastAPI server.
//
// GRACEFUL DEGRADATION IS THE POINT. The page probes /health once at load. If the API is
// not there, every live control is disabled with an explanation of what to start, and the
// static tabs are untouched — including the Results tab, which reads its own export and
// therefore shows the Phase 7 numbers whether or not anything is running. Nothing here ever
// falls back to a fabricated or cached value: if the server cannot answer, the page says so.

const API_CANDIDATES = ['http://127.0.0.1:8000', 'http://127.0.0.1:8077'];
const HEALTH_TIMEOUT_MS = 1500;

let apiBase = null;

// ---------------------------------------------------------------------------------------
// small helpers
// ---------------------------------------------------------------------------------------

const $ = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

/** Parse a comma-separated numeric list, refusing anything that is not fully numeric. */
function parseNumbers(text, expected, label) {
  const parts = String(text).split(',').map((p) => p.trim()).filter((p) => p !== '');
  if (parts.length !== expected) {
    throw new Error(`${label}: expected ${expected} comma-separated numbers, got ${parts.length}`);
  }
  return parts.map((part) => {
    const value = Number(part);
    if (!Number.isFinite(value)) throw new Error(`${label}: "${part}" is not a number`);
    return value;
  });
}

/** Format a probability so that both 0.42 and 3e-11 stay readable. */
function formatPc(pc) {
  if (pc === 0) return '0';
  if (pc >= 0.001) return pc.toFixed(6);
  const exponent = Math.floor(Math.log10(pc));
  const mantissa = pc / 10 ** exponent;
  return `${mantissa.toFixed(3)}<span class="exp">&times;10<sup>${exponent}</sup></span>`;
}

function showError(container, message, hint) {
  container.innerHTML = `<div class="error-box"><strong>${escapeHtml(message)}</strong>${
    hint ? `<div style="margin-top:5px">${escapeHtml(hint)}</div>` : ''
  }</div>`;
}

/** POST JSON and surface the API's structured error body rather than a bare status code. */
async function callApi(path, body) {
  const response = await fetch(apiBase + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(payload?.detail || `HTTP ${response.status}`);
    error.code = payload?.error;
    error.hint = payload?.hint;
    throw error;
  }
  return payload;
}

function renderProvenance(provenance) {
  if (!provenance) return '';
  const caveats = (provenance.caveats || [])
    .map((c) => `<li>${escapeHtml(c)}</li>`).join('');
  return `<div class="provenance">
    <strong>Method.</strong> ${escapeHtml(provenance.method || provenance.dataset || '—')}
    ${provenance.reproduction ? `<br><strong>Checked.</strong> ${escapeHtml(provenance.reproduction)}` : ''}
    ${caveats ? `<ul>${caveats}</ul>` : ''}
    <div style="margin-top:5px">code ${escapeHtml(provenance.code_version || '?')}
      · computed ${escapeHtml((provenance.computed_at || '').slice(0, 19))} UTC</div>
  </div>`;
}

// ---------------------------------------------------------------------------------------
// API discovery
// ---------------------------------------------------------------------------------------

async function probe(base) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), HEALTH_TIMEOUT_MS);
  try {
    const response = await fetch(`${base}/health`, { signal: controller.signal });
    if (!response.ok) return null;
    const health = await response.json();
    // Confirm it is *this* API and not merely something answering on the port. Port 8000 is
    // a popular default and another dev server responding 200 to /health would otherwise be
    // adopted silently, leaving the panels failing in confusing ways.
    if (!health?.checks?.sgp4 || !health?.checks?.tracss_store) return null;
    return health;
  } catch {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function discoverApi() {
  const strip = $('api-strip');
  const text = $('api-strip-text');

  for (const base of API_CANDIDATES) {
    const health = await probe(base);
    if (!health) continue;

    apiBase = base;
    const down = Object.entries(health.checks)
      .filter(([, check]) => !check.ok)
      .map(([name]) => name);

    strip.className = 'api-strip online';
    text.innerHTML = down.length
      ? `API live at <code>${escapeHtml(base)}</code> — degraded: ${escapeHtml(down.join(', '))}
         unavailable, so the panels that need them will say so rather than guess.`
      : `API live at <code>${escapeHtml(base)}</code> — benchmark, physics and agent all available.`;

    // /triage is the one panel that needs a credential; disable it precisely rather than
    // letting the user fire a request that can only fail.
    if (!health.checks.llm?.ok) {
      const submit = $('triage-submit');
      submit.disabled = true;
      submit.textContent = 'No LLM key configured';
    }
    return health;
  }

  strip.className = 'api-strip offline';
  text.innerHTML = `No API found. The 3D geometry, Distributions and Results tabs work from
    static exports and are unaffected. To enable the P<sub>c</sub> calculator and the Triage
    panel, run <code>uvicorn api.main:app</code> from the repository root and reload.`;

  for (const id of ['pc-submit', 'pc-example', 'triage-submit']) {
    const button = $(id);
    if (button) button.disabled = true;
  }
  $('pc-output').innerHTML =
    `<div class="result-card"><h3>Result</h3>
       <p class="spinner">The API is not running, so nothing can be computed here. This panel
       shows live results only — it will not display a stale or made-up number.</p></div>`;
  $('triage-output').innerHTML =
    `<div class="result-card"><h3>Verdicts</h3>
       <p class="spinner">The API is not running. The Results tab still shows what the agent
       scored when it was evaluated.</p></div>`;
  return null;
}

// ---------------------------------------------------------------------------------------
// Pc calculator
// ---------------------------------------------------------------------------------------

function readObject(prefix) {
  const [x, y, z] = parseNumbers($(`${prefix}-pos`).value, 3, `object ${prefix.slice(1)} position`);
  const [vx, vy, vz] = parseNumbers($(`${prefix}-vel`).value, 3, `object ${prefix.slice(1)} velocity`);
  const diagonal = parseNumbers($(`${prefix}-cov`).value, 3, `object ${prefix.slice(1)} covariance`);
  if (diagonal.some((v) => v <= 0)) {
    throw new Error(`object ${prefix.slice(1)} covariance: variances must be positive`);
  }
  const hbr = Number($(`${prefix}-hbr`).value);
  if (!Number.isFinite(hbr) || hbr <= 0) {
    throw new Error(`object ${prefix.slice(1)} hard-body radius must be positive`);
  }
  return {
    position_km: [x, y, z],
    velocity_kms: [vx, vy, vz],
    covariance: [
      [diagonal[0], 0, 0],
      [0, diagonal[1], 0],
      [0, 0, diagonal[2]],
    ],
    hard_body_radius_m: hbr,
  };
}

function conditioningRow(label, report) {
  if (!report) return '';
  const repaired = report.was_conditioned;
  return `<div class="kv">
    <dt>${escapeHtml(label)}</dt>
    <dd>${repaired ? '<span style="color:var(--warn)">repaired</span>' : 'untouched'}
        · cond ${Number(report.condition_number).toExponential(2)}</dd>
  </div>`;
}

function renderPc(result) {
  const repaired = result.conditioning_2d.was_conditioned || result.conditioning_3d.was_conditioned;
  $('pc-output').innerHTML = `
    <div class="result-card">
      <h3>Probability of collision</h3>
      <div class="bignum">${formatPc(result.pc)}</div>
      <div style="color:var(--ink-faint);font-size:11.5px;margin-top:2px">
        log<sub>10</sub> P<sub>c</sub> =
        ${result.log10_pc === null ? '−∞' : result.log10_pc.toFixed(4)}
      </div>
      ${result.pc < 1e-10 ? `<div class="notice" style="margin-top:10px">
        This is below the <strong>1e-10 floor</strong> at which TraCSS stops reporting. In the
        benchmark a value here would appear censored, as a bound rather than a number.</div>` : ''}
    </div>

    <div class="result-card">
      <h3>Geometry</h3>
      <div class="kv"><dt>Miss distance</dt><dd>${result.miss_distance_km.toFixed(6)} km</dd></div>
      <div class="kv"><dt>Relative speed</dt><dd>${result.relative_speed_kms.toFixed(4)} km/s</dd></div>
      <div class="kv"><dt>Combined hard-body radius</dt><dd>${result.combined_hard_body_radius_m} m</dd></div>
      <div class="kv"><dt>Mahalanobis, 3D</dt><dd>${result.mahalanobis_distance_3d.toFixed(4)}</dd></div>
      <div class="kv"><dt>Mahalanobis, encounter plane</dt><dd>${result.mahalanobis_distance_2d.toFixed(4)}</dd></div>
    </div>

    <div class="result-card">
      <h3>Covariance conditioning</h3>
      ${conditioningRow('Combined 3×3', result.conditioning_3d)}
      ${conditioningRow('Projected 2×2', result.conditioning_2d)}
      ${repaired ? `<div class="notice" style="margin-top:9px;margin-bottom:0">
        <strong>This P<sub>c</sub> rests on a repaired covariance.</strong> An eigenvalue was
        floored to make the matrix invertible. The number is still computed, but it is not on
        the same footing as one from a healthy covariance.</div>`
      : `<div style="color:var(--ink-faint);font-size:11px;margin-top:7px">
           Both matrices were positive-definite as supplied. Nothing was repaired.</div>`}
      ${renderProvenance(result.provenance)}
    </div>`;
}

async function loadBenchmarkExample() {
  const button = $('pc-example');
  button.disabled = true;
  button.textContent = 'Loading…';
  try {
    const response = await fetch(
      `${apiBase}/events?source=sfsh&limit=1&exclude_floored=true&order_by=pc_desc`
    );
    const payload = await response.json();
    if (!response.ok || !payload.events?.length) {
      throw new Error(payload.detail || 'no events returned');
    }
    const event = payload.events[0];

    // /events returns the published summary, not the state vectors, so this fills in what
    // it does carry and leaves the rest as it is. It is a starting point for the form, not
    // a reconstruction of the event -- the resulting Pc will not match the published one.
    $('o1-hbr').value = event.object1_hbr_m ?? 5;
    $('o2-hbr').value = event.object2_hbr_m ?? 5;
    $('o2-pos').value = `7000, 0, ${event.miss_distance_km.toFixed(4)}`;
    $('o1-pos').value = '7000, 0, 0';

    $('pc-output').innerHTML = `<div class="result-card">
      <h3>Loaded ${escapeHtml(event.event_id)}</h3>
      <div class="kv"><dt>Published P<sub>c</sub></dt><dd>${event.pc.toExponential(4)}</dd></div>
      <div class="kv"><dt>Miss distance</dt><dd>${event.miss_distance_km.toFixed(4)} km</dd></div>
      <div class="kv"><dt>Relative speed</dt><dd>${event.relative_speed_kms.toFixed(3)} km/s</dd></div>
      <div class="kv"><dt>Hard-body radii</dt><dd>${event.object1_hbr_m} m + ${event.object2_hbr_m} m</dd></div>
      <div class="notice" style="margin-top:10px;margin-bottom:0">
        The hard-body radii and the miss distance are this event's real values. The state
        vectors and covariances are <strong>not</strong> — <code>/events</code> returns the
        published summary, not the full state, so the form keeps its placeholder geometry.
        Computing now will not reproduce the published P<sub>c</sub>, and should not be read
        as if it had.
      </div>
    </div>`;
  } catch (error) {
    showError($('pc-output'), 'Could not load an example event.', error.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Load a real benchmark event';
  }
}

function wirePcCalculator() {
  $('pc-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!apiBase) return;

    const button = $('pc-submit');
    let body;
    try {
      body = {
        object1: readObject('o1'),
        object2: readObject('o2'),
        covariance_frame: $('pc-frame').value,
      };
    } catch (error) {
      showError($('pc-output'), 'Check the inputs.', error.message);
      return;
    }

    button.disabled = true;
    $('pc-output').innerHTML = '<p class="spinner">Computing…</p>';
    try {
      renderPc(await callApi('/pc', body));
    } catch (error) {
      showError(
        $('pc-output'),
        error.code === 'pc_undefined' ? 'Pc is undefined for these inputs.' : 'Request failed.',
        `${error.message}${error.hint ? ` — ${error.hint}` : ''}`
      );
    } finally {
      button.disabled = false;
    }
  });

  $('pc-example').addEventListener('click', loadBenchmarkExample);
}

// ---------------------------------------------------------------------------------------
// triage
// ---------------------------------------------------------------------------------------

function renderVerdicts(payload) {
  const parts = payload.verdicts.map((verdict) => {
    if (verdict.error) {
      return `<div class="verdict">
        <h4>${escapeHtml(verdict.series_id)}</h4>
        <div class="error-box" style="margin:0">${escapeHtml(verdict.error)}</div>
      </div>`;
    }

    if (!verdict.in_scope) {
      return `<div class="verdict">
        <h4>${escapeHtml(verdict.series_id)}</h4>
        <div class="pair">
          <div class="baseline"><div class="who">Baseline (used)</div>
            <div class="val">${verdict.baseline_risk.toFixed(3)}</div></div>
          <div class="agent"><div class="who">Agent</div>
            <div class="val" style="color:var(--ink-faint)">—</div></div>
        </div>
        <div class="reasoning">Latest visible risk is below the −7.0 alert threshold, so the
          agent was not invoked and no LLM call was made. The baseline stands.</div>
      </div>`;
    }

    const moved = verdict.predicted_final_risk - verdict.baseline_risk;
    const direction = Math.abs(moved) < 0.005
      ? 'left the baseline where it was'
      : `moved the estimate ${moved > 0 ? 'up' : 'down'} by ${Math.abs(moved).toFixed(2)}`;

    const cites = (verdict.evidence_cited || [])
      .map((c) => `${escapeHtml(c.field)} = ${escapeHtml(c.value)}`).join(' · ');

    return `<div class="verdict">
      <h4>${escapeHtml(verdict.series_id)}</h4>
      <div class="pair">
        <div class="baseline"><div class="who">Baseline — the better arm</div>
          <div class="val">${verdict.baseline_risk.toFixed(3)}</div></div>
        <div class="agent"><div class="who">Agent — ${escapeHtml(verdict.confidence || '')} confidence</div>
          <div class="val">${verdict.predicted_final_risk.toFixed(3)}</div></div>
      </div>
      <div style="font-size:11px;color:var(--ink-faint);margin-bottom:6px">
        The agent ${direction}, and predicted the risk
        ${verdict.will_collapse ? 'will collapse' : 'will not collapse'} before TCA.
      </div>
      <div class="reasoning">${escapeHtml(verdict.reasoning || '')}</div>
      ${cites ? `<div class="cites">cited: ${cites}</div>` : ''}
    </div>`;
  });

  $('triage-output').innerHTML = `
    <div class="result-card">
      <h3>${payload.answered} answered · ${payload.failed} failed of ${payload.requested}</h3>
      ${parts.join('')}
      ${renderProvenance(payload.provenance)}
    </div>`;
}

function wireTriage() {
  $('triage-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!apiBase) return;

    const ids = $('triage-ids').value.split(',').map((s) => s.trim()).filter(Boolean);
    if (!ids.length) {
      showError($('triage-output'), 'Enter at least one series id.', 'For example: test:100');
      return;
    }

    const button = $('triage-submit');
    button.disabled = true;
    $('triage-output').innerHTML =
      `<p class="spinner">Running the agent over ${ids.length} series — one LLM call each…</p>`;
    try {
      renderVerdicts(await callApi('/triage', { series_ids: ids, split: $('triage-split').value }));
    } catch (error) {
      showError(
        $('triage-output'),
        error.code === 'llm_unavailable' ? 'No LLM credential configured.' : 'Request failed.',
        `${error.message}${error.hint ? ` — ${error.hint}` : ''}`
      );
    } finally {
      button.disabled = false;
    }
  });
}

// ---------------------------------------------------------------------------------------
// Phase 7 results — static, so this tab works with nothing running
// ---------------------------------------------------------------------------------------

function renderResults(data) {
  const rows = data.arms.map((arm) => {
    const cls = arm.is_baseline ? 'baseline' : (arm.is_agent ? 'agent' : '');
    return `<tr class="${cls}">
      <td><strong>${escapeHtml(arm.label)}</strong><span class="desc">${escapeHtml(arm.description)}</span></td>
      <td><strong>${arm.L.toFixed(4)}</strong></td>
      <td>${arm.mse_hr === null ? '—' : arm.mse_hr.toFixed(4)}</td>
      <td>${arm.f2 === null ? '—' : arm.f2.toFixed(4)}</td>
      <td>${arm.precision === null ? '—' : arm.precision.toFixed(3)}</td>
      <td>${arm.recall === null ? '—' : arm.recall.toFixed(3)}</td>
    </tr>`;
  }).join('');

  const comparison = data.agent_vs_b1;
  const leaderboard = Object.entries(data.published_leaderboard || {})
    .map(([name, value]) => `<div class="kv"><dt>${escapeHtml(name)}</dt><dd>${value}</dd></div>`)
    .join('');

  $('results-output').innerHTML = `
    <div class="headline-box">
      <div class="big">${escapeHtml(data.headline)}</div>
      <p style="margin:6px 0 0;font-size:12.5px;color:var(--ink-dim)">${escapeHtml(data.metric)}</p>
    </div>

    <div class="result-card">
      <h3>Every arm, scored once on the held-out test set</h3>
      <table class="results">
        <thead><tr>
          <th>Arm</th><th>L</th><th>MSE<sub>HR</sub></th><th>F₂</th><th>Precision</th><th>Recall</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <div style="color:var(--ink-faint);font-size:11px;margin-top:9px">
        ${data.test_events?.toLocaleString?.() ?? data.test_events} test events,
        ${data.test_high_risk} of them truly high-risk
        (${data.test_high_risk_pct}%). Green is the baseline, red is the agent.
      </div>
    </div>

    <div class="result-card">
      <h3>Agent versus baseline — paired bootstrap</h3>
      <div class="kv"><dt>Median difference (agent − B1)</dt>
        <dd>${comparison.median_difference.toFixed(4)}</dd></div>
      <div class="kv"><dt>95% interval</dt>
        <dd>[${comparison.ci_low.toFixed(4)}, ${comparison.ci_high.toFixed(4)}]</dd></div>
      <div class="kv"><dt>Resamples favouring the agent</dt>
        <dd>${(100 * comparison.fraction_favouring_agent).toFixed(1)}% of
            ${comparison.resamples.toLocaleString()}</dd></div>
      <div class="provenance">${escapeHtml(comparison.note)}</div>
    </div>

    <div class="result-card">
      <h3>Against the published 2019 leaderboard</h3>
      ${leaderboard}
      <div class="provenance">
        <strong>Source.</strong> ${escapeHtml(data.published_source)}.
        Our B1 reproduced the published LRP to four decimal places and our constant −5 arm
        reproduced CRP to three significant figures, which is what licenses comparing the
        rest of this table against it.
      </div>
    </div>

    <div class="result-card">
      <h3>Provenance</h3>
      <div class="provenance" style="border-top:none;margin-top:0;padding-top:0">
        ${escapeHtml(data.provenance)}
        <div style="margin-top:6px">Frozen manifest HEAD
          <code>${escapeHtml((data.frozen_manifest_head || '').slice(0, 12))}</code>,
          committed before the test set was scored.</div>
      </div>
    </div>`;
}

async function loadResults() {
  try {
    const response = await fetch('./data/phase7_results.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    renderResults(await response.json());
  } catch (error) {
    showError(
      $('results-output'),
      'Could not load the Phase 7 export.',
      `${error.message} — regenerate it with: python scripts/export_frontend_data.py`
    );
  }
}

// ---------------------------------------------------------------------------------------

wirePcCalculator();
wireTriage();
loadResults();
discoverApi();
