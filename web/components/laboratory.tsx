"use client";

import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent, type ReactNode, type RefObject } from "react";
import Link from "next/link";
import { gsap } from "gsap";
import { ArrowDownRight, ArrowRight, Check, ChevronDown, CircleHelp, FlaskConical, LoaderCircle, Radio, RotateCcw, ScanLine, Sparkles } from "lucide-react";
import { apiRequest, useServiceHealth } from "@/lib/api";
import { useMotion } from "@/lib/motion";
import type { PcResult, TriagePayload } from "@/lib/types";
import "./laboratory.css";

type Frame = "uvw" | "eci";
type Mode = "physics" | "agent";
type ObjectInputs = { position: string; velocity: string; covariance: string; radius: string };
type Inputs = { object1: ObjectInputs; object2: ObjectInputs; frame: Frame };
type Computation = { result: PcResult; inputs: Inputs; comparison?: { uvw: number; eci: number } };
type RecordedTriage = { payload: TriagePayload; recorded: boolean; requestLabel: string };
type BenchmarkEvent = { event_id: string; pc: number | null; miss_distance_km: number; relative_speed_kms: number; object1_hbr_m: number | null; object2_hbr_m: number | null };
type BenchmarkResponse = { events: BenchmarkEvent[]; provenance?: Record<string, unknown> };

const DEFAULTS: Inputs = {
  object1: { position: "7000, 0, 0", velocity: "0, 7.5, 0", covariance: "0.17, 433.5, 0.42", radius: "5" },
  object2: { position: "7000.2, 0.1, 0.35", velocity: "2.0, 3.0, 6.5", covariance: "0.19, 487.5, 0.43", radius: "3" },
  frame: "uvw",
};

function probabilityParts(value: number) {
  if (!Number.isFinite(value) || value < 0) return null;
  if (value === 0) return { mantissa: "0", exponent: 0 };
  const exponent = Math.floor(Math.log10(value));
  return { mantissa: (value / 10 ** exponent).toFixed(3), exponent };
}

function Probability({ value }: { value: number }) {
  const parts = probabilityParts(value);
  if (!parts) return <>Unavailable</>;
  if (value === 0) return <>0</>;
  return <>{parts.mantissa}<span className="lab-exponent"> × 10<sup>{parts.exponent}</sup></span></>;
}

function percentage(value: number) {
  if (value === 0) return "0%";
  const percent = value * 100;
  return `${percent < 0.0001 ? percent.toExponential(3) : Number(percent.toPrecision(4))}%`;
}

function parseVector(value: string, label: string) {
  const parts = value.split(",").map((part) => part.trim());
  if (parts.length !== 3 || parts.some((part) => !part || !Number.isFinite(Number(part)))) {
    throw new Error(`${label}: enter three numbers separated by commas.`);
  }
  return parts.map(Number);
}

function parseObject(input: ObjectInputs, label: string) {
  const diagonal = parseVector(input.covariance, `${label} covariance`);
  if (diagonal.some((value) => value <= 0)) throw new Error(`${label}: covariance variances must be greater than zero.`);
  const radius = Number(input.radius);
  if (!Number.isFinite(radius) || radius <= 0 || radius > 1000) throw new Error(`${label}: radius must be greater than zero and at most 1,000 metres.`);
  return {
    position_km: parseVector(input.position, `${label} position`),
    velocity_kms: parseVector(input.velocity, `${label} velocity`),
    covariance: diagonal.map((value, row) => diagonal.map((_, column) => row === column ? value : 0)),
    hard_body_radius_m: radius,
  };
}

function errorMessage(error: unknown) {
  if (error instanceof Error) {
    const hint = (error as Error & { hint?: string }).hint;
    return `${error.message}${hint ? ` ${hint}` : ""}`;
  }
  return "The request could not complete. Check the local service and try again.";
}

async function timedRequest<T>(path: string, options?: RequestInit, timeout = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    return await apiRequest<T>(path, { ...options, signal: controller.signal });
  } catch (error) {
    if (controller.signal.aborted) throw new Error(`No response within ${timeout / 1000} seconds. The server may still be processing; reconnect before trying again.`);
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function moveToOutput(ref: RefObject<HTMLDivElement | null>) {
  requestAnimationFrame(() => {
    const output = ref.current;
    if (!output || output.closest("[hidden]")) return;
    output.focus({ preventScroll: true });
    const reducedMotion = document.documentElement.dataset.motion
      ? document.documentElement.dataset.motion === "reduced"
      : window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    output.scrollIntoView({ block: "start", behavior: reducedMotion ? "instant" : "smooth" });
  });
}

function Detail({ title, children, open = false }: { title: string; children: ReactNode; open?: boolean }) {
  return <details className="lab-details" open={open || undefined}><summary>{title}<ChevronDown size={15} aria-hidden="true" /></summary><div>{children}</div></details>;
}

function DataRow({ label, children }: { label: ReactNode; children: ReactNode }) {
  return <div className="lab-data-row"><dt>{label}</dt><dd>{children}</dd></div>;
}

function Provenance({ data }: { data: unknown }) {
  if (!data) return null;
  return <Detail title="Method, source & full provenance"><p className="lab-small">Original response metadata is preserved for inspection.</p><pre className="lab-json">{JSON.stringify(data, null, 2)}</pre></Detail>;
}

function FrameStudy({ frame }: { frame: Frame }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const { enabled } = useMotion();
  useLayoutEffect(() => {
    if (!svgRef.current) return;
    const first = gsap.to(svgRef.current.querySelector(".lab-uncertainty-a"), { rotation: frame === "uvw" ? -22 : 0, svgOrigin: "156 104", duration: enabled ? 0.85 : 0, ease: "power3.inOut" });
    const second = gsap.to(svgRef.current.querySelector(".lab-uncertainty-b"), { rotation: frame === "uvw" ? 48 : 0, svgOrigin: "300 130", duration: enabled ? 0.85 : 0, ease: "power3.inOut" });
    return () => { first.kill(); second.kill(); };
  }, [frame, enabled]);
  return <div className="lab-frame-study">
    <div className="lab-frame-label"><span className="mono">FIG. 01 / THE FRAME EXPERIMENT</span><span>{frame.toUpperCase()}</span></div>
    <svg ref={svgRef} viewBox="0 0 456 216" role="img" aria-labelledby="lab-diagram-title lab-diagram-desc">
      <title id="lab-diagram-title">{`Position uncertainty in ${frame.toUpperCase()} coordinates`}</title><desc id="lab-diagram-desc">Conceptual illustration. Each ellipse represents positional uncertainty. In UVW, its axes follow the object’s orbit. In ECI, both objects use the same inertial directions. Changing the declared frame changes the meaning of the input numbers.</desc>
      <defs><pattern id="lab-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="currentColor" strokeWidth=".5" opacity=".13" /></pattern></defs>
      <rect width="456" height="216" fill="url(#lab-grid)" />
      <path d="M20 164Q180 116 430 36M16 42Q213 36 416 197" className="lab-orbit-path" />
      <path d="M156 104L300 130" className="lab-miss-line" />
      <g className="lab-uncertainty-a"><ellipse cx="156" cy="104" rx="65" ry="24" className="lab-ellipse-a" /><path d="M80 104H232M156 66V142" className="lab-axis-a" /></g>
      <g className="lab-uncertainty-b"><ellipse cx="300" cy="130" rx="63" ry="25" className="lab-ellipse-b" /><path d="M224 130H376M300 91V169" className="lab-axis-b" /></g>
      <circle cx="156" cy="104" r="5" className="lab-point-a" /><circle cx="300" cy="130" r="5" className="lab-point-b" />
      <text x="106" y="37" className="lab-svg-label">OBJECT 01</text><text x="315" y="197" className="lab-svg-label">OBJECT 02</text><text x="206" y="98" className="lab-svg-note">separation</text>
    </svg>
    <div className="lab-frame-caption"><span><i className="lab-dot" /> Position uncertainty</span><span>Conceptual · not to scale</span></div>
  </div>;
}

function ObjectFields({ number, value, update, disabled }: { number: 1 | 2; value: ObjectInputs; update: (key: keyof ObjectInputs, value: string) => void; disabled: boolean }) {
  const fields: { key: keyof ObjectInputs; label: string; unit: string }[] = [
    { key: "position", label: "Position", unit: "km · ECI x, y, z" },
    { key: "velocity", label: "Velocity", unit: "km/s · ECI vx, vy, vz" },
    { key: "covariance", label: "Covariance diagonal", unit: "km² · three variances" },
    { key: "radius", label: "Hard-body radius", unit: "metres" },
  ];
  return <fieldset className={`lab-object lab-object-${number}`} disabled={disabled}>
    <legend><span className="lab-object-number">0{number}</span><span>Object {number}<small>{number === 1 ? "Primary object" : "Encountering object"}</small></span></legend>
    <div className="lab-object-fields">{fields.map(({ key, label, unit }) => <div className="field lab-field" key={key}>
      <label htmlFor={`o${number}-${key}`}>{label}<span>{unit}</span></label>
      <input id={`o${number}-${key}`} name={`o${number}-${key}`} type={key === "radius" ? "number" : "text"} min={key === "radius" ? 0.000001 : undefined} max={key === "radius" ? 1000 : undefined} step={key === "radius" ? "any" : undefined} value={value[key]} onChange={(event) => update(key, event.target.value)} required spellCheck={false} autoComplete="off" aria-describedby={key === "covariance" ? "lab-covariance-help" : undefined} />
    </div>)}</div>
  </fieldset>;
}

function PcOutput({ computation, stale }: { computation: Computation; stale: boolean }) {
  const { result, inputs, comparison } = computation;
  const repaired = result.conditioning_2d.was_conditioned || result.conditioning_3d.was_conditioned;
  const ratio = comparison && comparison.uvw > 0 ? comparison.eci / comparison.uvw : null;
  return <>
    {stale && <div className="notice lab-stale" role="status"><RotateCcw size={16} /><p><strong>Inputs changed.</strong> This result belongs to the previous inputs. Compute again to update it.</p></div>}
    <div className="lab-probability-card" data-lab-result>
      <div className="lab-result-heading"><span className="eyebrow">CALCULATED PROBABILITY</span><span className="lab-result-tag"><span /> LIVE RESULT</span></div>
      <div className="lab-pc-number"><Probability value={result.pc} /></div>
      <p className="lab-percent">{percentage(result.pc)} <span>under the supplied encounter model</span></p>
      <div className="lab-result-footer"><span>Alfano short-encounter method</span><span className="mono">{inputs.frame.toUpperCase()} INPUT</span></div>
    </div>
    <p className="lab-output-caption">One calculated encounter probability, conditional on geometry, object sizes and positional uncertainty. It does not establish whether a collision will occur.</p>
    {result.pc < 1e-10 && <div className="notice lab-bound-note">Below the inferred TraCSS reporting floor of 10<sup>−10</sup>. Benchmark values at that floor are treated as upper bounds.</div>}
    {comparison && <div className="lab-comparison-result" data-lab-result>
      <div className="lab-block-heading"><h3>Same inputs. Two declared frames.</h3><ScanLine size={19} /></div>
      <div className="lab-comparison-pair"><div><span className="eyebrow">UVW</span><strong><Probability value={comparison.uvw} /></strong></div><div><span className="eyebrow">ECI</span><strong><Probability value={comparison.eci} /></strong></div></div>
      <p>{ratio !== null && Number.isFinite(ratio) ? <><strong>{Number(ratio.toPrecision(3))}×</strong> ECI / UVW for these inputs. </> : "A finite ratio is unavailable for these inputs. "}The values describe different uncertainty orientations, not two estimates of the same physical covariance.</p>
    </div>}
    <div className="lab-output-block">
      <div className="lab-block-heading"><h3>The geometry behind the number.</h3><ArrowDownRight size={21} /></div>
      <dl className="lab-data-list"><DataRow label="Miss distance">{result.miss_distance_km.toFixed(6)} km</DataRow><DataRow label="Relative speed">{result.relative_speed_kms.toFixed(4)} km/s</DataRow><DataRow label="Combined hard-body radius">{result.combined_hard_body_radius_m} m</DataRow><DataRow label={<>log<sub>10</sub>(P<sub>c</sub>)</>}>{result.log10_pc === null ? "−∞" : result.log10_pc.toFixed(4)}</DataRow><DataRow label="Input covariance frame">{inputs.frame === "uvw" ? "Each object’s own UVW frame" : "Shared J2000 / ECI frame"}</DataRow></dl>
      <Detail title="Uncertainty distance & encounter plane"><p>Mahalanobis distance measures separation relative to position uncertainty. The encounter plane is perpendicular to relative motion; the probability integral is evaluated in that plane.</p><dl><DataRow label="Mahalanobis distance · 3D">{result.mahalanobis_distance_3d.toFixed(4)}</DataRow><DataRow label="Mahalanobis distance · encounter plane">{result.mahalanobis_distance_2d.toFixed(4)}</DataRow></dl><p className="lab-small">Projected covariance in km²</p><pre className="lab-json">{JSON.stringify(result.projected_covariance_km2, null, 2)}</pre></Detail>
      <Detail title={repaired ? "Covariance check · repair needed" : "Covariance check · no repair needed"}>
        <p>{repaired ? "Small eigenvalues were raised to a numerical floor so that the calculation could proceed. Interpret the probability with this repair in mind." : "Both covariance matrices could be used without a numerical repair. This checks the matrix, not the quality of the underlying observations."}</p>
        <dl><DataRow label="Combined 3 × 3 matrix">{result.conditioning_3d.was_conditioned ? "Repaired" : "Unchanged"}</DataRow><DataRow label="Condition number · 3D">{Number(result.conditioning_3d.condition_number).toExponential(3)}</DataRow><DataRow label="Projected 2 × 2 matrix">{result.conditioning_2d.was_conditioned ? "Repaired" : "Unchanged"}</DataRow><DataRow label="Condition number · 2D">{Number(result.conditioning_2d.condition_number).toExponential(3)}</DataRow></dl><pre className="lab-json">{JSON.stringify({ combined: result.conditioning_3d, projected: result.conditioning_2d }, null, 2)}</pre>
      </Detail>
      <Detail title="Exact inputs used for this calculation"><pre className="lab-json">{JSON.stringify({ ...inputs, units: { position: "km, J2000/ECI", velocity: "km/s, J2000/ECI", covariance: "km², diagonal only", radius: "m" } }, null, 2)}</pre></Detail>
      <Provenance data={result.provenance} />
    </div>
  </>;
}

function RiskNumber({ value }: { value: number | null | undefined }) {
  if (value == null || !Number.isFinite(value)) return <><strong className="lab-risk-number">—</strong><small>Not available</small></>;
  return <><strong className="lab-risk-number">{value.toFixed(3)}</strong><small>{value <= -30 ? "Negligible-risk floor · not exact" : <>P<sub>c</sub> ≈ <Probability value={10 ** value} /></>}</small></>;
}

function TriageOutput({ data }: { data: RecordedTriage }) {
  const { payload, recorded, requestLabel } = data;
  return <>
    <div className="lab-triage-result-heading" data-lab-result><span className="eyebrow">{recorded ? "FROM THE RESEARCH ARCHIVE" : "LIVE API RESPONSE"}</span><h2>{payload.answered} answered.<br /><span>{payload.failed} failed.</span></h2><p>{payload.requested} series requested · {requestLabel}</p></div>
    {recorded && <div className="notice lab-recorded-note"><Radio size={17} /><p><strong>Recorded example. No provider call.</strong> Original outputs from the frozen Phase 7 evaluation. The series shown here are independent of the IDs in the live form.</p></div>}
    <div className="lab-verdicts">{payload.verdicts.map((verdict, index) => <article className="lab-verdict" key={`${verdict.series_id}-${index}`} data-lab-result>
      <div className="lab-verdict-title"><span className="mono">{verdict.series_id}</span><span className="tag">{verdict.error ? "Request error" : verdict.in_scope ? "Agent invoked" : "Baseline retained"}</span></div>
      {verdict.error ? <div className="lab-error" role="alert">{verdict.error}</div> : <>
        <div className="lab-risk-pair"><div><span className="eyebrow">LATEST-CDM BASELINE</span><RiskNumber value={verdict.baseline_risk} /></div><div><span className="eyebrow">AGENT ESTIMATE</span>{verdict.in_scope ? <RiskNumber value={verdict.predicted_final_risk} /> : <><strong className="lab-risk-number lab-no-invocation">Not invoked</strong><small>Below the −7 scope threshold</small></>}</div></div>
        {verdict.in_scope ? <>
          <div className="lab-verdict-classification"><span className="lab-tiny-square" /><p>Agent classification: <strong>{verdict.will_collapse ? "risk resolves to negligible" : "elevated risk persists"}</strong>.</p></div>
          <Detail title="Read the agent’s explanation" open><p className="lab-model-reasoning">{verdict.reasoning || "No explanation supplied."}</p><p className="lab-small">Original model reasoning. Physical assertions in this text are not independently verified here.</p></Detail>
          <Detail title={`Cited evidence · ${verdict.evidence_cited?.length || 0} fields`}><dl>{(verdict.evidence_cited || []).map((cite, citeIndex) => <DataRow key={citeIndex} label={<code>{String(cite.field)}</code>}>{typeof cite.value === "object" ? JSON.stringify(cite.value) : String(cite.value)}</DataRow>)}</dl></Detail>
          <p className="lab-confidence">Model confidence: <strong>{verdict.confidence || "not supplied"}</strong>. This is a self-report, not a calibrated probability.</p>
        </> : <p className="lab-small">The latest visible log-risk is below −7. The workflow keeps the baseline and makes no model call for this series.</p>}
        <Detail title="Effective prediction & complete verdict"><p>The effective prediction is the value this workflow returns after applying its scope rule.</p><pre className="lab-json">{JSON.stringify(verdict, null, 2)}</pre></Detail>
      </>}
    </article>)}</div>
    <div className="lab-triage-footnote"><CircleHelp size={19} /><p>A persuasive explanation is not evidence of better prediction. The frozen evaluation favoured the latest-CDM baseline. <Link href="/evidence">Read the evaluation <ArrowRight size={13} /></Link></p></div>
    <Provenance data={payload.provenance} />
  </>;
}

export default function Laboratory() {
  const root = useRef<HTMLDivElement>(null);
  const physicsOutput = useRef<HTMLDivElement>(null);
  const agentOutput = useRef<HTMLDivElement>(null);
  const tabPhysics = useRef<HTMLButtonElement>(null);
  const tabAgent = useRef<HTMLButtonElement>(null);
  const { health, status, refresh } = useServiceHealth();
  const { enabled } = useMotion();
  const [mode, setMode] = useState<Mode>("physics");
  const [inputs, setInputs] = useState<Inputs>(DEFAULTS);
  const [computation, setComputation] = useState<Computation | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkResponse | null>(null);
  const [pcError, setPcError] = useState("");
  const [pcBusy, setPcBusy] = useState<"single" | "compare" | "benchmark" | null>(null);
  const [seriesIds, setSeriesIds] = useState("test:100, test:1001");
  const [split, setSplit] = useState<"test" | "train">("test");
  const [triage, setTriage] = useState<RecordedTriage | null>(null);
  const [triageError, setTriageError] = useState("");
  const [triageBusy, setTriageBusy] = useState<"live" | "recorded" | null>(null);

  const checks = health?.checks;
  const tracss = checks?.tracss_store as { ok?: boolean; sources?: Record<string, number> } | undefined;
  const kelvins = checks?.kelvins_store as { ok?: boolean; files?: string[] } | undefined;
  const llm = checks?.llm as { ok?: boolean } | undefined;
  const physicsReady = status === "online";
  const benchmarkReady = physicsReady && !!tracss?.ok && !!tracss.sources?.sfsh;
  const splitReady = !!kelvins?.ok && !!kelvins.files?.includes(`cdms_${split}.parquet`) && !!kelvins.files?.includes(`series_${split}.parquet`);
  const triageReady = physicsReady && !!llm?.ok && splitReady;
  const stale = !!computation && JSON.stringify(computation.inputs) !== JSON.stringify(inputs);
  const triageStatus = status === "checking" ? "Checking the live service…" : !physicsReady ? "Start the local API for live analysis. Recorded examples work immediately." : !splitReady ? `The ${split} Kelvins files are unavailable. Use the recorded example.` : !llm?.ok ? "A provider key is not configured. Use the recorded example or configure the live service." : "Live analysis available. Uncached, in-scope series may use a paid provider call.";

  useEffect(() => {
    const fromLocation = () => {
      const selected = new URLSearchParams(window.location.search).get("tab") || window.location.hash.slice(1);
      if (selected === "triage" || selected === "agent") setMode("agent");
      if (selected === "physics" || selected === "pc") setMode("physics");
    };
    fromLocation();
    window.addEventListener("hashchange", fromLocation);
    return () => window.removeEventListener("hashchange", fromLocation);
  }, []);

  useLayoutEffect(() => {
    const context = gsap.context(() => {
      gsap.fromTo(".lab-mode-panel:not([hidden]) [data-lab-reveal]", { y: enabled ? 22 : 0, opacity: enabled ? 0 : 1 }, { y: 0, opacity: 1, duration: enabled ? 0.65 : 0, stagger: enabled ? 0.075 : 0, ease: "power3.out", clearProps: "transform,opacity" });
    }, root);
    return () => context.revert();
  }, [mode, enabled]);

  useLayoutEffect(() => {
    if (!enabled) return;
    const context = gsap.context(() => {
      gsap.fromTo(".lab-mode-panel:not([hidden]) [data-lab-result]", { y: 18, opacity: 0 }, { y: 0, opacity: 1, duration: 0.55, stagger: 0.08, ease: "power2.out", clearProps: "transform,opacity" });
    }, root);
    return () => context.revert();
  }, [computation, triage, enabled]);

  function chooseMode(next: Mode) {
    setMode(next);
    const url = new URL(window.location.href);
    url.hash = next === "agent" ? "triage" : "physics";
    window.history.replaceState(null, "", url);
  }

  function tabKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? "physics" : event.key === "End" ? "agent" : mode === "physics" ? "agent" : "physics";
    chooseMode(next);
    (next === "physics" ? tabPhysics : tabAgent).current?.focus();
  }

  function updateObject(object: "object1" | "object2", key: keyof ObjectInputs, value: string) {
    setInputs((current) => ({ ...current, [object]: { ...current[object], [key]: value } }));
  }

  async function compute(compare = false) {
    if (!physicsReady || pcBusy) return;
    setPcError("");
    const captured = structuredClone(inputs);
    let body;
    try {
      body = { object1: parseObject(captured.object1, "Object 1"), object2: parseObject(captured.object2, "Object 2") };
    } catch (error) {
      setPcError(errorMessage(error));
      moveToOutput(physicsOutput);
      return;
    }
    setPcBusy(compare ? "compare" : "single");
    const request = (frame: Frame) => timedRequest<PcResult>("/pc", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...body, covariance_frame: frame }) });
    try {
      if (compare) {
        const [uvw, eci] = await Promise.all([request("uvw"), request("eci")]);
        setComputation({ result: captured.frame === "uvw" ? uvw : eci, inputs: captured, comparison: { uvw: uvw.pc, eci: eci.pc } });
      } else {
        setComputation({ result: await request(captured.frame), inputs: captured });
      }
    } catch (error) {
      setPcError(errorMessage(error));
    } finally {
      setPcBusy(null);
      moveToOutput(physicsOutput);
    }
  }

  async function loadBenchmark() {
    if (!benchmarkReady || pcBusy) return;
    setPcBusy("benchmark");
    setPcError("");
    try {
      const data = await timedRequest<BenchmarkResponse>("/events?source=sfsh&limit=1&exclude_floored=true&order_by=pc_desc");
      const event = data.events?.[0];
      if (!event || !Number.isFinite(event.miss_distance_km) || event.object1_hbr_m == null || event.object2_hbr_m == null) throw new Error("No benchmark row with usable dimensions was returned.");
      setInputs((current) => ({ ...current, object1: { ...current.object1, position: "7000, 0, 0", radius: String(event.object1_hbr_m) }, object2: { ...current.object2, position: `7000, 0, ${event.miss_distance_km}`, radius: String(event.object2_hbr_m) } }));
      setBenchmark(data);
    } catch (error) {
      setPcError(errorMessage(error));
      moveToOutput(physicsOutput);
    } finally {
      setPcBusy(null);
    }
  }

  function resetPhysics() {
    setInputs(structuredClone(DEFAULTS));
    setBenchmark(null);
    setPcError("");
  }

  async function runTriage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!triageReady || triageBusy) return;
    setTriageError("");
    const ids = seriesIds.split(",").map((id) => id.trim()).filter(Boolean);
    let invalid = "";
    if (ids.length < 1 || ids.length > 10) invalid = "Enter between 1 and 10 series IDs, separated by commas.";
    else if (new Set(ids).size !== ids.length) invalid = "Remove duplicate series IDs before running the analysis.";
    else if (ids.some((id) => !new RegExp(`^${split}:\\d+$`).test(id))) invalid = `Use IDs matching the selected split, such as ${split}:100.`;
    if (invalid) {
      setTriageError(invalid);
      moveToOutput(agentOutput);
      return;
    }
    setTriageBusy("live");
    try {
      const payload = await timedRequest<TriagePayload>("/triage", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ series_ids: ids, split }) }, 180000);
      setTriage({ payload, recorded: false, requestLabel: `${split} split · ${ids.join(", ")}` });
    } catch (error) {
      setTriageError(errorMessage(error));
    } finally {
      setTriageBusy(null);
      moveToOutput(agentOutput);
    }
  }

  async function loadRecorded() {
    if (triageBusy) return;
    setTriageError("");
    setTriageBusy("recorded");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("/data/triage_example.json", { signal: controller.signal });
      if (!response.ok) throw new Error(`The recorded example could not load (HTTP ${response.status}).`);
      const payload: TriagePayload = await response.json();
      if (!Array.isArray(payload.verdicts)) throw new Error("The recorded example has an unexpected format.");
      setTriage({ payload, recorded: true, requestLabel: "Original Phase 7 archive" });
    } catch (error) {
      setTriageError(controller.signal.aborted ? "The recorded file took too long to load. Please try again." : errorMessage(error));
    } finally {
      clearTimeout(timer);
      setTriageBusy(null);
      moveToOutput(agentOutput);
    }
  }

  return <div className="page-shell lab-page" ref={root}>
    <header className="lab-page-heading"><div><p className="eyebrow"><span className="lab-tiny-square" /> 03 / THE LABORATORY</p><h1 className="page-title">Question the<br /><em>probability.</em></h1></div><div className="lab-heading-aside"><FlaskConical size={29} strokeWidth={1} /><p>Change the inputs.<br />Observe the calculation.<br /><strong>Keep the evidence.</strong></p></div></header>
    <div className="lab-topbar"><div className="lab-tab-list" role="tablist" aria-label="Laboratory tools"><button ref={tabPhysics} id="lab-tab-physics" role="tab" aria-selected={mode === "physics"} aria-controls="lab-panel-physics" tabIndex={mode === "physics" ? 0 : -1} onKeyDown={tabKey} onClick={() => chooseMode("physics")}><span>01</span> Collision physics<ScanLine size={16} /></button><button ref={tabAgent} id="lab-tab-agent" role="tab" aria-selected={mode === "agent"} aria-controls="lab-panel-agent" tabIndex={mode === "agent" ? 0 : -1} onKeyDown={tabKey} onClick={() => chooseMode("agent")}><span>02</span> Agent reasoning<Sparkles size={16} /></button></div><div className="lab-service"><span className={`lab-service-dot lab-service-${status}`} /><span role="status">{status === "checking" ? "Checking service" : physicsReady ? "Physics connected" : "Static preview available"}</span><button className="lab-icon-button" onClick={refresh} disabled={status === "checking"} aria-label="Reconnect to live services" title="Reconnect"><RotateCcw size={14} className={status === "checking" ? "lab-spinning" : ""} /></button></div></div>

    <section className="lab-mode-panel" id="lab-panel-physics" role="tabpanel" aria-labelledby="lab-tab-physics" hidden={mode !== "physics"}>
      <div className="lab-intro-grid" data-lab-reveal><div className="lab-intro-copy"><p className="eyebrow">AN EXPERIMENT IN UNCERTAINTY</p><h2>Distance is only<br />half the story.</h2><p className="lede">The same separation can lead to very different collision probabilities. Object size and the direction of position uncertainty complete the picture.</p><div className="lab-experiment-note"><span className="lab-experiment-value">6.39<small>×</small></span><p>Approximate ECI / UVW ratio for the default inputs. Use <strong>Compare frames</strong> to reproduce it live.</p></div></div><FrameStudy frame={inputs.frame} /></div>
      <div className="lab-workspace-grid">
        <div className="lab-form-column" data-lab-reveal>
          <div className="lab-section-title"><div><span className="eyebrow">A / INPUTS</span><h2>Construct an encounter.</h2></div><button className="lab-reset-button" type="button" onClick={resetPhysics} disabled={!!pcBusy}><RotateCcw size={14} /> Reset example</button></div>
          <p className="lab-small">Illustrative states at closest approach. Positions and velocities use J2000 / ECI. The two objects share one declared covariance convention.</p>
          <form id="pc-form" onSubmit={(event) => { event.preventDefault(); void compute(); }}>
            <div className="lab-objects-grid"><ObjectFields number={1} value={inputs.object1} update={(key, value) => updateObject("object1", key, value)} disabled={!!pcBusy} /><ObjectFields number={2} value={inputs.object2} update={(key, value) => updateObject("object2", key, value)} disabled={!!pcBusy} /></div>
            <div className="lab-frame-selector"><label htmlFor="pc-frame">Orient the uncertainty.<span>The frame changes what the numbers mean.</span></label><select id="pc-frame" value={inputs.frame} disabled={!!pcBusy} onChange={(event) => setInputs((current) => ({ ...current, frame: event.target.value as Frame }))}><option value="uvw">UVW · each object’s orbital axes</option><option value="eci">ECI · shared inertial axes</option></select></div>
            <p className="lab-small" id="lab-covariance-help">Covariance entries are variances, in km². The form sets cross-covariances to zero. Hard-body radii represent physical object size, in metres.</p>
            <Detail title="What is the difference between UVW and ECI?"><p><strong>UVW</strong> follows each object’s own orbit: radial, along-track and cross-track. <strong>ECI</strong> uses shared inertial directions. Local covariances must each be rotated before being combined.</p><p>Changing only the frame declaration changes the physical interpretation of the same numbers. The comparison demonstrates this sensitivity; it does not make one frame intrinsically more accurate.</p><p>The default covariance magnitudes come from an SFSH example. The states are illustrative and do not reconstruct that original event.</p></Detail>
            <div className="lab-main-actions"><button className="button button-dark" id="pc-submit" type="submit" disabled={!physicsReady || !!pcBusy}>{pcBusy === "single" ? <LoaderCircle size={17} className="lab-spinning" /> : <ArrowRight size={17} />} {pcBusy === "single" ? "Calculating…" : "Compute probability"}</button><button className="button button-outline" id="pc-compare" type="button" onClick={() => void compute(true)} disabled={!physicsReady || !!pcBusy}>{pcBusy === "compare" ? <LoaderCircle size={16} className="lab-spinning" /> : <ScanLine size={16} />}{pcBusy === "compare" ? "Comparing…" : "Compare frames"}</button></div>
            <p className="lab-service-copy" id="pc-status" role="status">{status === "checking" ? "Checking the calculation service…" : physicsReady ? "Live computation available. No LLM or provider key is needed." : "Start the local API and reconnect to compute. You can explore every input now."}</p>
          </form>
          <div className="lab-benchmark-import"><div><span className="eyebrow">OR START WITH PUBLISHED DIMENSIONS</span><p>Borrow object sizes and separation from an actual SFSH row.</p></div><button className="lab-text-button" id="pc-example" type="button" onClick={() => void loadBenchmark()} disabled={!benchmarkReady || !!pcBusy}>{pcBusy === "benchmark" ? "Loading dimensions…" : "Use benchmark dimensions"}<ArrowDownRight size={17} /></button>{!benchmarkReady && status !== "checking" && <p className="lab-small">This import needs the API and ingested SFSH store.</p>}</div>
          {benchmark && <div className="notice lab-benchmark-note"><strong>Partial benchmark dimensions loaded.</strong><p>Only miss distance and radii were imported. Positions were arranged to match that separation; velocities and covariances remain as entered. A new calculation will not reproduce the published event.</p><Detail title="Inspect the original benchmark row"><dl><DataRow label="Event ID">{benchmark.events[0].event_id}</DataRow><DataRow label="Published probability">{benchmark.events[0].pc === null ? "Unavailable" : <Probability value={benchmark.events[0].pc} />}</DataRow><DataRow label="Miss distance">{benchmark.events[0].miss_distance_km.toFixed(6)} km</DataRow><DataRow label="Relative speed · not imported">{benchmark.events[0].relative_speed_kms.toFixed(3)} km/s</DataRow><DataRow label="Hard-body radii">{benchmark.events[0].object1_hbr_m} m + {benchmark.events[0].object2_hbr_m} m</DataRow></dl><Provenance data={benchmark.provenance} /></Detail></div>}
        </div>
        <div className="lab-output-column" data-lab-reveal><div className="lab-section-title"><div><span className="eyebrow">B / OBSERVATION</span><h2>The result, with context.</h2></div><span className="lab-bracket">[ P<sub>c</sub> ]</span></div><div ref={physicsOutput} className="lab-output" tabIndex={-1} aria-live="polite" aria-busy={pcBusy === "single" || pcBusy === "compare"}>
          {pcError && <div className="lab-error" role="alert"><strong>Calculation could not complete.</strong><p>{pcError}</p></div>}
          {(pcBusy === "single" || pcBusy === "compare") && <div className="lab-progress"><LoaderCircle size={18} className="lab-spinning" /><span>Integrating probability. Checking covariance.</span></div>}
          {computation ? <PcOutput computation={computation} stale={stale} /> : <div className="lab-result-placeholder"><div className="lab-placeholder-cross lab-cross-top" /><span className="eyebrow">AWAITING AN EXPERIMENT</span><div className="lab-placeholder-symbol">P<sub>c</sub><span>= ?</span></div><p>Choose your inputs.<br />We will keep the geometry, probability<br />and numerical checks together.</p><div className="lab-placeholder-cross lab-cross-bottom" /></div>}
        </div><div className="lab-method-check"><Check size={18} /><div><strong>A checked numerical method.</strong><p>11,059 uncensored comparisons from 20,000 sampled TraCSS records agreed within 0.1%. This is reproduction of a published calculation, not validation against collision outcomes.</p><Detail title="What does this validation cover?"><p>The Alfano implementation was compared with the published TraCSS probability column. After excluding 8,941 censored values, all 11,059 comparable values agreed within 0.1%; the median ratio was approximately 0.999994.</p><p>Every live result preserves the conditioning report, exact inputs and response provenance. The encounter model assumes the supplied states describe a short encounter at closest approach.</p></Detail></div></div></div>
      </div>
    </section>

    <section className="lab-mode-panel" id="lab-panel-agent" role="tabpanel" aria-labelledby="lab-tab-agent" hidden={mode !== "agent"}>
      <div className="lab-agent-intro" data-lab-reveal><div><p className="eyebrow">READ THE REASONING. TEST THE CLAIM.</p><h2>Can an explanation<br />improve an estimate?</h2><p className="lede">The agent reads successive conjunction reports and predicts whether elevated risk will persist. Here, its reasoning sits beside a simpler alternative: keep the latest reported risk.</p></div><div className="lab-agent-score"><span className="eyebrow">THE FROZEN EVALUATION / LOWER IS BETTER</span><div><span><strong>0.6940</strong><small>Latest-risk baseline</small></span><span className="lab-score-divider">/</span><span><strong>1.6606</strong><small>LLM agent</small></span></div><p>The agent’s loss was 2.4× as large.</p><Link href="/evidence">Examine the complete evidence <ArrowRight size={15} /></Link></div></div>
      <div className="lab-workspace-grid lab-agent-grid">
        <div className="lab-form-column" data-lab-reveal><div className="lab-section-title"><div><span className="eyebrow">A / A HISTORY OF REPORTS</span><h2>Choose a risk history.</h2></div></div>
          <div className="lab-recorded-start"><span className="lab-archive-icon"><Radio size={25} strokeWidth={1.2} /></span><div><h3>Start with the archive.</h3><p>Two authentic model outputs, ready to inspect. No backend, credential or provider call.</p></div><button className="button button-dark" type="button" id="triage-example" onClick={() => void loadRecorded()} disabled={!!triageBusy}>{triageBusy === "recorded" ? <LoaderCircle size={16} className="lab-spinning" /> : <ArrowRight size={16} />}{triageBusy === "recorded" ? "Opening archive…" : "View recorded example"}</button></div>
          <form id="triage-form" onSubmit={runTriage} className="lab-triage-form"><div className="lab-divider-caption"><span>OR REQUEST A LIVE ANALYSIS</span></div><div className="field lab-field"><label htmlFor="triage-ids">Series IDs<span>Up to 10 · separated by commas</span></label><textarea id="triage-ids" rows={3} value={seriesIds} onChange={(event) => setSeriesIds(event.target.value)} spellCheck={false} required disabled={!!triageBusy} /></div><div className="field lab-field"><label htmlFor="triage-split">Dataset split<span>IDs must match this prefix</span></label><select id="triage-split" value={split} disabled={!!triageBusy} onChange={(event) => setSplit(event.target.value as "test" | "train")}><option value="test">Test · held-out evaluation split</option><option value="train">Train · development split</option></select></div><button className="button button-outline" id="triage-submit" type="submit" disabled={!triageReady || !!triageBusy}>{triageBusy === "live" ? <LoaderCircle size={17} className="lab-spinning" /> : <Sparkles size={17} />}{triageBusy === "live" ? "Analysing series…" : "Run live analysis"}</button><p className="lab-service-copy" id="triage-status" role="status">{triageStatus}</p></form>
          <div className="lab-risk-key"><span className="eyebrow">A SMALL GUIDE TO VERY SMALL NUMBERS</span><h3>More negative. Less probable.</h3><div className="lab-risk-key-scale"><div><strong>−7</strong><small>1 in 10 million</small></div><ArrowRight size={20} /><div><strong>−5</strong><small>1 in 100,000</small></div><ArrowRight size={20} /><div><strong>−3</strong><small>1 in 1,000</small></div></div><p>Risk = log<sub>10</sub>(P<sub>c</sub>). A value of −30 is the workflow’s negligible-risk floor; it is not an exact measured probability.</p></div>
          <Detail title="Which messages can the agent see?"><p>A Conjunction Data Message (CDM) reports an encounter’s estimated geometry, risk and uncertainty. A series contains successive reports about one encounter. Inputs stop at least two days before closest approach; the agent predicts the final calculated risk.</p><p>The agent is invoked when the latest visible log-risk is at least <strong>−7</strong>. Below that, the workflow retains the latest-CDM baseline without a model call. The evaluation’s separate high-risk threshold is <strong>−6</strong>.</p><p>Kelvins series are anonymised and have relative times, not catalogue identities and absolute dates. These histories cannot be matched to objects in the 3D scene. Their final labels describe calculated probabilities, not observed collisions.</p></Detail>
        </div>
        <div className="lab-output-column" data-lab-reveal><div className="lab-section-title"><div><span className="eyebrow">B / COMPARE THE JUDGEMENT</span><h2>The reasoning, exposed.</h2></div><span className="lab-bracket">[ AI ]</span></div><div className="lab-output" ref={agentOutput} tabIndex={-1} aria-live="polite" aria-busy={!!triageBusy}>
          {triageError && <div className="lab-error" role="alert"><strong>Analysis could not complete.</strong><p>{triageError}</p></div>}
          {triageBusy && <div className="lab-progress"><LoaderCircle size={18} className="lab-spinning" /><span>{triageBusy === "recorded" ? "Opening the recorded examples…" : "Reading series. In-scope cases may call the model or reuse a cached response. This can take a few minutes."}</span></div>}
          {triage ? <TriageOutput data={triage} /> : <div className="lab-result-placeholder lab-agent-placeholder"><div className="lab-placeholder-cross lab-cross-top" /><span className="eyebrow">EVIDENCE BEFORE CONVICTION</span><div className="lab-agent-placeholder-symbol"><span>01</span><span /><span>02</span></div><p>A baseline.<br />An agent’s judgement.<br /><strong>A comparison you can inspect.</strong></p><div className="lab-placeholder-cross lab-cross-bottom" /></div>}
        </div></div>
      </div>
    </section>
    <footer className="lab-local-footer"><span className="mono">RESEARCH LABORATORY / NOT AN OPERATIONAL DECISION SYSTEM</span><Link href="/evidence">Let the results speak <ArrowRight size={16} /></Link></footer>
  </div>;
}
