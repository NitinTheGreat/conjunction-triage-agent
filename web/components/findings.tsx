"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { gsap } from "gsap";
import { Pause, Play, StepForward } from "lucide-react";
import { useMotion } from "@/lib/motion";
import { count, fixed, messagesUsing, percent, reusedIn, signed, type ConditionKey, type Findings } from "@/lib/findings";
import type { GlobeHover } from "@/components/lineage-globe";
import { BankStrip, DecisionRule, DevelopmentChart, ForestPlot, FrontierChart, MissDumbbell, OverlapChart, RealContrastChart, ValuesTable, WindowsDiagram, contrastName, contrastQuestion } from "@/components/findings-charts";
import "./evidence.css";
import "./findings.css";

const LineageGlobe = dynamic(() => import("@/components/lineage-globe"), { ssr: false, loading: () => <div className="fd-globe-loading"><span />Placing the observations</div> });

const CONDITION_LABEL: Record<string, string> = { no_reuse: "No reuse", overlap_50: "50% overlap", overlap_90: "90% overlap", solution_reissue: "Solution reissue", new_information: "New information", burst_reissue: "Burst reissue", exact_replay: "Exact replay" };
const ARM_ORDER = ["singleton", "latest_metadata", "grouped", "oracle_lineage_weight"];
const WORDS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen", "Twenty"];
const spell = (value: number) => WORDS[value] ?? count(value);

function Stamp({ kind, children }: { kind: "confirmatory" | "development" | "real"; children: React.ReactNode }) {
  return <span className={`fd-stamp fd-stamp-${kind}`}>{children}</span>;
}

export default function FindingsPage() {
  const { enabled } = useMotion();
  const [data, setData] = useState<Findings | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [conditionKey, setConditionKey] = useState<ConditionKey>("overlap_90");
  const [message, setMessage] = useState(3);
  const [highlight, setHighlight] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [hover, setHover] = useState<GlobeHover | null>(null);
  const [contrast, setContrast] = useState("P1");
  const [split, setSplit] = useState<"training_oof" | "historical_test">("training_oof");
  const [step, setStep] = useState<number | null>(null);
  const root = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/data/paper_findings.json", { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("The findings export is unavailable."); return response.json(); })
      .then((result: Findings) => {
        if (!result.scientific?.decisions?.some((item) => item.id === "P1")) throw new Error("The findings export does not contain the primary result.");
        setData(result); setError("");
      })
      .catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => setMessage((value) => (value + 1) % 6), 1700);
    return () => window.clearInterval(timer);
  }, [playing]);

  useEffect(() => {
    if (!data || !root.current || !enabled) return;
    const context = gsap.context(() => {}, root);
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        context.add(() => gsap.from(entry.target, { y: 30, autoAlpha: 0, duration: .85, ease: "power3.out" }));
        observer.unobserve(entry.target);
      });
    }, { threshold: .06 });
    root.current.querySelectorAll("[data-fd-reveal]").forEach((element) => observer.observe(element));
    return () => { observer.disconnect(); context.revert(); };
  }, [data, enabled]);

  const onGlobeHover = useCallback((target: GlobeHover | null) => {
    const box = stage.current?.getBoundingClientRect();
    setHover(target && box ? { ...target, x: target.x - box.left, y: target.y - box.top } : null);
    setHighlight(target?.kind === "observation" ? target.id : null);
  }, []);
  const onSelectMessage = useCallback((index: number) => { setPlaying(false); setMessage(index); }, []);

  const condition = useMemo(() => data?.design.conditions.find((item) => item.key === conditionKey) ?? null, [data, conditionKey]);
  const registered = useMemo(() => new Set(data?.register.map((row) => row.id) ?? []), [data]);
  const reg = (id: string) => registered.has(id) ? <span className="fd-reg" title="Row of the claim register that regenerates this number">{id}</span> : null;

  if (error) return <section className="page-shell fd-page"><p className="eyebrow">The findings / stored export</p><h1 className="page-title">The findings could not be loaded.</h1><p className="lede" role="alert">{error}</p><button className="button button-dark" onClick={() => { setError(""); setAttempt((value) => value + 1); }}>Try again</button></section>;
  if (!data || !condition) return <section className="page-shell fd-page" aria-busy="true"><p className="eyebrow">The findings / stored export</p><h1 className="page-title">Reading the results.</h1><p className="lede" role="status">Loading the frozen evaluation…</p></section>;

  const science = data.scientific;
  const p1 = science.decisions.find((item) => item.id === "P1")!;
  const s1 = science.decisions.find((item) => item.id === "S1")!;
  const s5 = science.decisions.find((item) => item.id === "S5")!;
  const selected = science.decisions.find((item) => item.id === contrast) ?? p1;
  const loss = (arm: string, key: string) => science.losses.find((item) => item.arm === arm && item.condition === key)!;
  const rate = (arm: string, key: string) => science.rates.find((item) => item.arm === arm && item.condition === key)!;
  const windows = condition.windows;
  const repeated = reusedIn(windows, message);
  const shareRepeated = 1 - condition.unique_observations / condition.message_observation_pairs;
  const hovered = hover?.kind === "observation" ? messagesUsing(windows, hover.id) : [];
  const overlap90 = data.design.conditions.find((item) => item.key === "overlap_90");
  const realRows = data.real.contrasts.filter((item) => item.split === split);
  const r1 = (key: string) => data.real.contrasts.find((item) => item.split === key && item.id === "R1")!;
  const cohort = data.real.cohort;
  const bias = data.development.p1_banks.filter((item) => item.key === "bias");
  const steps = [
    { title: "Development on exposed banks", body: "Tuning, precision planning, simulator sensitivity and interval validation used only scenarios generated for development. Those results shaped the protocol; none of them counts as confirmation." },
    { title: "Protocol frozen", body: `On ${data.protocol.frozen_utc.slice(0, 10)} at ${data.protocol.frozen_utc.slice(11, 16)} UTC the claim, contrast, margin, sample sizes, interval method and multiplicity rule were written to a machine-readable protocol (SHA-256 ${data.protocol.sha256.slice(0, 12)}…), with ${data.protocol.pinned_files} code files pinned by git blob id. No held-out scenario existed yet.` },
    { title: "Held-out banks generated", body: `${data.protocol.training_banks} independent training banks of ${count(data.protocol.training_scenarios)} scenarios and one evaluation bank of ${count(data.protocol.evaluation_scenarios)}, in a noise configuration never used in development (variance ratio 4, rotated ${data.protocol.configuration.rotation_degrees}°).` },
    { title: "Predictions sealed", body: `${count(science.labelled_rows)} predictions were written and hashed before any evaluation label was read.` },
    { title: "Frozen analysis", body: `Bank-combined studentized bootstrap intervals (${count(data.protocol.bootstrap_resamples)} resamples) and Holm's procedure for four secondary hypotheses. Every reported number was reconstructed exactly from the saved predictions.` },
    { title: "Still to come", body: "An independent reproduction by someone outside this project has not yet been carried out. A pre-run check of the decision rule by an independent analyst was waived." },
  ];

  return <article ref={root} className="page-shell fd-page">
    <header className="fd-intro" data-fd-reveal>
      <div className="fd-kicker"><p className="eyebrow">The findings / 04 · Observation reuse</p><span className="fd-stamp-plain">FROZEN PROTOCOL · {data.protocol.frozen_utc.slice(0, 10)}</span></div>
      <h1 className="fd-headline">{spell(overlap90?.windows.length ?? 6)} messages.<br />{spell(overlap90?.unique_observations ?? 0)} <em>observations.</em></h1>
      <div className="fd-intro-bottom">
        <p className="lede">A close approach between two satellites is usually reported many times before it happens. Successive conjunction messages can be computed from mostly the same tracking observations. We built a simulation in which every observation has a name, froze the analysis before the test data existed, and measured what this reuse does to a forecaster that reads the whole history.</p>
        <a href="#lineage" className="ev-text-link">Follow one encounter <span aria-hidden="true">↘</span></a>
      </div>
      <div className="fd-headline-stats">
        <div><span className="fd-stat">{signed(p1.mean)}</span><p>nats of extra loss for the history summary at 90% overlap, relative to the latest message. Frozen 95% interval {fixed(p1.lower)} to {fixed(p1.upper)}. {reg("V01")}</p></div>
        <div><span className="fd-stat">{signed(s1.mean)}</span><p>advantage left to the history summary over the latest message at 90% overlap: essentially none. {reg("V04")}</p></div>
        <div><span className="fd-stat">{percent(rate("singleton", "overlap_90").miss_rate)}</span><p>of high-risk scenarios missed at the nominal 95% review threshold, up from {percent(rate("singleton", "no_reuse").miss_rate)} without reuse. {reg("V10")} {reg("V14")}</p></div>
      </div>
    </header>

    <section id="lineage" className="fd-lineage" aria-labelledby="lineage-heading" data-fd-reveal>
      <div className="fd-globe-stage" ref={stage}>
        <LineageGlobe windows={windows} availability={data.design.availability_days} messageTimes={data.design.message_times_days} message={message} highlight={highlight} paused={!enabled} onHover={onGlobeHover} onSelectMessage={onSelectMessage} />
        {hover && <div className="fd-tip fd-globe-tip" role="status" style={{ left: hover.x, top: hover.y }}>
          {hover.kind === "observation" ? <><strong>Observation {hover.id}</strong><span>Available {fixed(data.design.availability_days[hover.id], 2)} days before closest approach</span><span>{hovered.length ? `Used by ${hovered.map((index) => `m${index + 1}`).join(", ")}` : "Not used by any message in this condition"}</span></> : <><strong>Message m{hover.index + 1}</strong><span>Published {fixed(data.design.message_times_days[hover.index], 2)} days before closest approach</span><span>Select to show its observations</span></>}
        </div>}
        <p className="fd-globe-note">Illustrative geometry: eight days are compressed into one orbit. Windows are the simulator&apos;s exact definitions. Drag to rotate.</p>
      </div>
      <div className="fd-controls">
        <p className="eyebrow">Follow one encounter</p>
        <h2 id="lineage-heading">Each message is a window<br />onto the <em>same</em> observations.</h2>
        <p className="fd-controls-copy">Dots on the bright track are tracking observations, placed where they became available. Each message m1–m6 is computed from a window of ten of them. The second orbit crosses the first at the time of closest approach (TCA).</p>
        <div className="fd-conditions" role="group" aria-label="Reuse condition">{data.design.conditions.map((item) => <button key={item.key} aria-pressed={item.key === conditionKey} onClick={() => { setConditionKey(item.key); setHighlight(null); }}>{item.label}</button>)}</div>
        <p className="fd-condition-note" aria-live="polite">{condition.note}</p>
        <div className="fd-messages" role="group" aria-label="Messages">{windows.map((window, index) => {
          const old = reusedIn(windows, index).length;
          return <button key={index} aria-pressed={index === message} onClick={() => onSelectMessage(index)} aria-label={`Message m${index + 1}: ${window.length - old} new and ${old} reused observations`}>
            <span>m{index + 1}</span><i className="fd-message-bar" aria-hidden="true"><b style={{ flexGrow: window.length - old }} /><em style={{ flexGrow: old }} /></i>
          </button>;
        })}</div>
        <div className="fd-play-row">
          <button className="button button-primary" onClick={() => setPlaying((value) => !value)} aria-pressed={playing}>{playing ? <Pause size={15} /> : <Play size={15} />}{playing ? "Pause the sequence" : "Play the sequence"}</button>
          <button className="icon-button fd-step" aria-label="Next message" onClick={() => onSelectMessage((message + 1) % 6)}><StepForward size={16} /></button>
        </div>
        <dl className="fd-readout" aria-live="polite">
          <div><dt>Message m{message + 1}</dt><dd>{windows[message].length} observations, <strong>{repeated.length}</strong> already used by an earlier message</dd></div>
          <div><dt>All six messages</dt><dd><strong>{condition.unique_observations}</strong> distinct observations behind {condition.message_observation_pairs} message–observation pairs{condition.key !== "new_information" && shareRepeated > 0 ? ` (${percent(shareRepeated, 0)} repeats)` : ""}</dd></div>
        </dl>
        <div className="fd-globe-legend"><span><i className="is-fresh" />New to this message</span><span><i className="is-reused" />Used by an earlier message</span><span><i className="is-used" />Used by another message</span><span><i className="is-future" />Arrives after the two-day cutoff; final label only</span></div>
      </div>
    </section>

    <section className="fd-section" aria-labelledby="design-heading" data-fd-reveal>
      <div className="fd-section-top">
        <div><p className="eyebrow">The design</p><h2 id="design-heading">Same latest message.<br />Different <em>history.</em></h2></div>
        <div className="fd-copy">
          <p>Every scenario has one latent encounter, eighty noisy observations and one final label computed from all of them. Only the first sixty are visible to any message. The conditions change which of those sixty each message uses, and nothing else.</p>
          <p>In every reuse condition the latest message is computed from the same window, observations 50 to 59. A forecaster that reads only the latest message therefore cannot be affected by reuse. It is the comparator. The new-information condition is the control in which a longer history really does carry more evidence.</p>
        </div>
      </div>
      <div className="fd-panel">
        <div className="fd-panel-head"><span className="eyebrow">{condition.label} · select a row to move the globe</span><span className="fd-legend-inline"><i className="is-fresh" />new <i className="is-reused" />already used</span></div>
        <WindowsDiagram condition={condition} message={message} onMessage={onSelectMessage} highlight={highlight} onHighlight={setHighlight} />
        <p className="fd-fine">{data.design.replay_note} Exact replays are removed before any summary is computed, so they cannot change a history feature.</p>
        <ValuesTable caption="Observation windows by condition" head={["Condition", "Windows (first–last ID)", "Message–observation pairs", "Distinct observations"]} rows={data.design.conditions.map((item) => [item.label, item.windows.map((window) => `${window[0]}–${window[window.length - 1]}`).join(", "), item.message_observation_pairs, item.unique_observations])} />
      </div>
    </section>

    <section className="fd-section" aria-labelledby="response-heading" data-fd-reveal>
      <div className="fd-section-top">
        <div><Stamp kind="confirmatory">Confirmatory · held-out configuration</Stamp><h2 id="response-heading">More messages.<br />Worse <em>forecasts.</em></h2></div>
        <div className="fd-copy">
          <p>Without reuse, the history summary is much better than the latest message: {fixed(loss("singleton", "no_reuse").mean)} against {fixed(loss("latest_metadata", "no_reuse").mean)} nats of clipped log loss {reg("V11")} {reg("V12")}. At 90% overlap it rises to {fixed(loss("singleton", "overlap_90").mean)} {reg("V13")}, level with a forecaster that ignores the history altogether. When one solution is republished six times, it ends up worse.</p>
          <p>Grouping messages by their orbit-determination metadata, or weighting them with the true observation lineage, does not change the picture. Both follow the same curve.</p>
        </div>
      </div>
      <div className="fd-panel">
        <div className="fd-panel-head"><span className="eyebrow">Mean over {data.protocol.training_banks} training banks × {count(data.protocol.evaluation_scenarios)} scenarios · whiskers span the bank means · select a condition</span></div>
        <OverlapChart losses={science.losses} selected={conditionKey} onSelect={(key) => setConditionKey(key as ConditionKey)} />
        {conditionKey === "new_information" && <p className="fd-fine">The new-information condition is not on this axis because its latest message also changes. There the history summary scores {fixed(loss("singleton", "new_information").mean)} and the latest message {fixed(loss("latest_metadata", "new_information").mean)}.</p>}
        <ValuesTable caption="Mean clipped log loss by forecaster and condition" head={["Forecaster", ...["no_reuse", "overlap_50", "overlap_90", "solution_reissue", "new_information", "burst_reissue", "exact_replay"].map((key) => CONDITION_LABEL[key])]} rows={ARM_ORDER.map((arm) => [data.arms[arm], ...["no_reuse", "overlap_50", "overlap_90", "solution_reissue", "new_information", "burst_reissue", "exact_replay"].map((key) => fixed(loss(arm, key).mean, 4))])} />
      </div>
    </section>

    <section className="fd-section" aria-labelledby="test-heading" data-fd-reveal>
      <div className="fd-section-top">
        <div><Stamp kind="confirmatory">Confirmatory · frozen decision rule</Stamp><h2 id="test-heading">One test,<br />decided in <em>advance.</em></h2></div>
        <div className="fd-copy">
          <p>The primary contrast, P1, is the extra loss that 90% overlap adds to the history summary, minus the extra loss it adds to the latest message (which is zero by construction). Before any held-out scenario existed, we fixed a margin of {data.protocol.margin} nats and a rule: confirm if the whole 95% interval lies above the margin, call the effect not material if it lies below, and otherwise report it as inconclusive.</p>
          <p>The interval combines scenario sampling with the variation between independently trained models, which development showed cannot be ignored.</p>
        </div>
      </div>
      <div className="fd-panel"><DecisionRule p1={p1} margin={data.protocol.margin} /><p className="fd-verdict">Material degradation confirmed. {reg("V01")} {reg("V02")} {reg("V03")}</p></div>
      <div className="fd-test-grid">
        <div className="fd-panel"><div className="fd-panel-head"><span className="eyebrow">All frozen contrasts · select a row</span></div><ForestPlot decisions={science.decisions} selected={contrast} onSelect={setContrast} /></div>
        <aside className="fd-panel fd-contrast-detail" aria-live="polite">
          <p className="eyebrow">{contrastName(selected.id)}</p>
          <p className="fd-question">{contrastQuestion(selected.id)}</p>
          <dl>
            <div><dt>Estimate</dt><dd>{signed(selected.mean, 4)}</dd></div>
            <div><dt>95% interval</dt><dd>{signed(selected.lower, 4)} to {signed(selected.upper, 4)}</dd></div>
            <div><dt>Null</dt><dd>{selected.null == null ? "none (exploratory)" : signed(selected.null, 2)}</dd></div>
            <div><dt>Outcome</dt><dd>{selected.decision ? "Material degradation confirmed" : selected.holm_rejected ? `Null rejected after Holm (p = ${selected.p_value?.toFixed(4)})` : "Reported, not tested"}</dd></div>
          </dl>
          {science.banks[selected.id] && <><p className="fd-fine">One dot per independently trained model bank; the vertical line is their mean.</p><BankStrip values={science.banks[selected.id]} mean={selected.mean} margin={selected.null} label={contrastName(selected.id)} /></>}
        </aside>
      </div>
      <ValuesTable caption="Frozen contrasts" head={["Contrast", "Estimate", "Lower", "Upper", "Null", "p", "Outcome"]} rows={science.decisions.map((item) => [contrastName(item.id), fixed(item.mean, 4), fixed(item.lower, 4), fixed(item.upper, 4), item.null == null ? "—" : fixed(item.null, 2), item.p_value == null ? "—" : item.p_value.toFixed(4), item.decision ? "confirmed" : item.holm_rejected ? "rejected (Holm)" : "exploratory"])} />
      <p className="fd-fine">The four secondary p-values sit at the bootstrap floor of 1/{count(data.protocol.bootstrap_resamples + 1)}. Solution reissue degrades the history summary by {fixed(s5.mean)} nats.</p>
    </section>

    <section className="fd-section" aria-labelledby="miss-heading" data-fd-reveal>
      <div className="fd-section-top">
        <div><Stamp kind="confirmatory">Confirmatory run · descriptive</Stamp><h2 id="miss-heading">Reuse turns into<br /><em>missed</em> alerts.</h2></div>
        <div className="fd-copy"><p>Each model flags the scenarios it would send for review at a threshold chosen to catch 95% of high-risk training scenarios. At 90% overlap the history summary stops flagging {count(science.misses.new)} positive bank–scenario pairs that it flagged without reuse {reg("V16")}, and starts flagging only {count(science.misses.recovered)} that it had missed {reg("V17")}, out of {count(science.misses.positives)} {reg("V18")}.</p><p className="fd-fine">Banks share their evaluation scenarios, so the pooled counts are descriptive rather than independent trials.</p></div>
      </div>
      <div className="fd-miss-grid">
        <div className="fd-tiles"><div><span className="fd-stat">{count(science.misses.new)}</span><p>newly missed</p></div><div><span className="fd-stat">{count(science.misses.recovered)}</span><p>newly caught</p></div><div><span className="fd-stat">{percent(science.misses.new / science.misses.positives)}</span><p>of positive pairs lost to reuse</p></div></div>
        <div className="fd-panel"><MissDumbbell rates={science.rates} /></div>
      </div>
    </section>

    <section className="fd-section" aria-labelledby="dev-heading" data-fd-reveal>
      <div className="fd-section-top">
        <div><Stamp kind="development">Exposed development · before the freeze</Stamp><h2 id="dev-heading">It held before<br />the freeze, <em>too.</em></h2></div>
        <div className="fd-copy"><p>Before freezing the protocol we trained independent model banks under four other noise configurations. The degradation exceeded the margin in every isotropic, anisotropic and doubled-noise bank. With a shared observation bias it sat at the margin ({fixed(Math.min(...bias.map((item) => item.mean)))} to {fixed(Math.max(...bias.map((item) => item.mean)))}).</p><p className="fd-fine">An earlier apparent reversal under shared bias ({signed(data.development.bias_transfer_mean)}) came from models trained without bias and evaluated with it. These are development results that shaped the protocol, not confirmation.</p></div>
      </div>
      <div className="fd-panel"><DevelopmentChart banks={data.development.p1_banks} margin={data.protocol.margin} /></div>
    </section>

    <section className="fd-section" aria-labelledby="real-heading" data-fd-reveal>
      <div className="fd-section-top">
        <div><Stamp kind="real">Exposed retrospective · real messages</Stamp><h2 id="real-heading">Real messages<br />point the same <em>way.</em></h2></div>
        <div className="fd-copy"><p>On the public Kelvins conjunction data, the history summary is also worse than the latest message: by {signed(r1("training_oof").mean, 4)} nats out of fold on {count(cohort.train.eligible_events)} training events {reg("R01")}, and by {signed(r1("historical_test").mean)} on the {count(cohort.test.eligible_events)}-event historical test split {reg("R03")}.</p><p className="fd-fine">Public messages do not record which observations they reuse, so this agrees in direction but cannot show why. The test split has a much higher share of high-risk events ({percent(cohort.test.positives / cohort.test.eligible_events)}) than training ({percent(cohort.train.positives / cohort.train.eligible_events)}), and its labels have long been public.</p></div>
      </div>
      <div className="fd-split" role="group" aria-label="Data split"><button aria-pressed={split === "training_oof"} onClick={() => setSplit("training_oof")}>Training cohort · out of fold</button><button aria-pressed={split === "historical_test"} onClick={() => setSplit("historical_test")}>Historical test split</button></div>
      <div className="fd-real-grid">
        <div className="fd-panel"><div className="fd-panel-head"><span className="eyebrow">Paired differences in clipped log loss</span></div><RealContrastChart contrasts={data.real.contrasts} split={split} /></div>
        <div className="fd-panel"><div className="fd-panel-head"><span className="eyebrow">Missed positives against review effort · dots mark the nominal 95% threshold</span></div><FrontierChart curves={data.real.frontiers[split]} metrics={data.real.metrics} split={split} /></div>
      </div>
      <ValuesTable caption="Real-data contrasts" head={["Contrast", "Mean", "Event interval", "Mission interval", "Missions"]} rows={realRows.map((item) => [item.id, signed(item.mean, 4), `${signed(item.event_lower, 4)} to ${signed(item.event_upper, 4)}`, `${signed(item.mission_lower, 4)} to ${signed(item.mission_upper, 4)}`, item.missions])} />
    </section>

    <section className="fd-section" aria-labelledby="method-heading" data-fd-reveal>
      <div className="fd-section-top"><div><p className="eyebrow">How the test was kept honest</p><h2 id="method-heading">Frozen first.<br />Measured <em>once.</em></h2></div><p className="fd-copy">Select a step to read what it involved.</p></div>
      <ol className="fd-timeline">{steps.map((item, index) => <li key={item.title} className={step === index ? "is-open" : ""}><button aria-expanded={step === index} onClick={() => setStep(step === index ? null : index)}><span>{String(index + 1).padStart(2, "0")}</span>{item.title}</button>{step === index && <p>{item.body}</p>}</li>)}</ol>
    </section>

    <section className="fd-section fd-limits" aria-labelledby="limits-heading" data-fd-reveal>
      <div><p className="eyebrow">Boundaries</p><h2 id="limits-heading">What this<br />does not <em>show.</em></h2></div>
      <ul>
        <li><strong>A model, not an orbit.</strong> The simulator is a static two-dimensional encounter plane with a synthetic label: the final recorded risk class, not whether a collision happened.</li>
        <li><strong>One held-out configuration.</strong> The frozen test covers one noise configuration and a stress population with many near misses; review fractions are not operational workload.</li>
        <li><strong>Bounded forecasters.</strong> Logistic models on a declared grid, with {science.selections.at_upper_C} of {science.selections.models} selections at its edge. No claim is made about every possible model.</li>
        <li><strong>Real data cannot attribute cause.</strong> Public conjunction messages carry no observation lineage, few positives and a strong shift between splits.</li>
        <li><strong>Not yet reproduced independently.</strong> The analysis reconstructs exactly from saved predictions, but nobody outside the project has repeated it.</li>
      </ul>
    </section>

    <footer className="fd-record" data-fd-reveal>
      <p className="eyebrow">The record stays visible</p>
      <details className="ev-details"><summary>Provenance and the claim register</summary>
        <p>This page reads <code>/data/paper_findings.json</code>, written by <code>{"research/web_findings.py"}</code> from committed result bundles. The small codes beside numbers are rows of the claim register, each of which regenerates its value from those bundles.</p>
        <dl className="ev-definitions"><dt>Protocol</dt><dd><code>{data.protocol.sha256}</code></dd><dt>Frozen at</dt><dd><code>{data.protocol.git_head_at_freeze.slice(0, 7)}</code>, {data.protocol.frozen_utc.slice(0, 19).replace("T", " ")} UTC</dd><dt>Label</dt><dd>{data.protocol.label}</dd><dt>Population</dt><dd>{data.protocol.population}</dd><dt>Inputs</dt><dd>{Object.keys(data.inputs_sha256).length} committed files, hashed in the export</dd></dl>
      </details>
      <div className="ev-next"><span>See the earlier agent evaluation, or explore real encounter geometry.</span><div className="fd-next-links"><Link href="/evidence" className="button button-outline">The evidence</Link><Link href="/observatory" className="button button-dark">Open the observatory <span aria-hidden="true">↗</span></Link></div></div>
    </footer>
  </article>;
}
