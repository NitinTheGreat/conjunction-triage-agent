"use client";

import { useEffect, useRef, useState } from "react";
import { gsap } from "gsap";
import Link from "next/link";
import { useMotion } from "../lib/motion";
import "./evidence.css";

type Arm = {
  key: string; label: string; description: string; L: number;
  mse_hr: number | null; f2: number | null; precision: number | null; recall: number | null;
  is_baseline: boolean; is_agent: boolean;
};
type Results = {
  arms: Arm[]; test_events: number; test_high_risk: number; test_high_risk_pct: number;
  agent_vs_b1: { median_difference: number; ci_low: number; ci_high: number;
    resamples: number; fraction_favouring_agent: number; note: string; };
  published_leaderboard: Record<string, { L: number; mse_hr: number | null; f2: number | null }>;
  published_source: string; frozen_manifest_head: string; provenance: string;
};

const number = (value: number | null, places = 4) => value == null ? "—" : value.toFixed(places);
const leaderboardNames: Record<string, string> = {
  CRP_baseline_constant_minus5: "Constant-risk baseline · CRP",
  LRP_baseline_latest_risk: "Latest-risk baseline · LRP",
  winner_sesc: "Challenge winner · sesc",
  tenth_spacemeister: "10th place · spacemeister",
};

export default function Evidence() {
  const { enabled } = useMotion();
  const [data, setData] = useState<Results | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [measure, setMeasure] = useState<"loss" | "recall">("loss");
  const root = useRef<HTMLElement>(null);
  const comparison = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/data/phase7_results.json", { signal: controller.signal })
      .then((response) => { if (!response.ok) throw new Error("The stored evaluation is unavailable."); return response.json(); })
      .then((result: Results) => {
        if (!Array.isArray(result.arms) || !result.arms.some((arm) => arm.is_baseline) || !result.arms.some((arm) => arm.is_agent)) {
          throw new Error("The evaluation file does not contain the required comparison.");
        }
        setData(result); setError("");
      })
      .catch((reason: Error) => { if (reason.name !== "AbortError") setError(reason.message); });
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    if (!data || !root.current || !enabled) return;
    const context = gsap.context(() => {}, root);
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        context.add(() => gsap.from(entry.target, { y: 35, autoAlpha: 0, duration: .9, ease: "power3.out" }));
        observer.unobserve(entry.target);
      });
    }, { threshold: .08 });
    root.current.querySelectorAll("[data-evidence-reveal]").forEach((element) => observer.observe(element));
    return () => { observer.disconnect(); context.revert(); };
  }, [data, enabled]);

  useEffect(() => {
    if (!data || !comparison.current || !enabled) return;
    const context = gsap.context(() => {}, comparison);
    const observer = new IntersectionObserver((entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      context.add(() => gsap.fromTo(".ev-comparison-fill", { scaleX: 0 }, { scaleX: 1, transformOrigin: "left", duration: 1.1, stagger: .14, ease: "power3.out" }));
      observer.disconnect();
    }, { threshold: .1 });
    observer.observe(comparison.current);
    return () => { observer.disconnect(); context.revert(); };
  }, [data, measure, enabled]);

  if (error) return <section className="page-shell ev-page"><p className="eyebrow">Evidence / stored evaluation</p><h1 className="page-title">The record could not be loaded.</h1><p className="lede" role="alert">{error}</p><button className="button button-dark" onClick={() => { setError(""); setAttempt((value) => value + 1); }}>Try again</button></section>;
  if (!data) return <section className="page-shell ev-page" aria-busy="true"><p className="eyebrow">Evidence / stored evaluation</p><h1 className="page-title">Reading the record.</h1><p className="lede" role="status">Loading the original Phase 7 results…</p></section>;

  const baseline = data.arms.find((arm) => arm.is_baseline)!;
  const agent = data.arms.find((arm) => arm.is_agent)!;
  const ratio = agent.L / baseline.L;
  const paired = data.agent_vs_b1;
  const ordered = [...data.arms].sort((a, b) => a.L - b.L);
  const maxComparison = measure === "loss" ? agent.L * 1.1 : 1;

  return <article ref={root} className="page-shell ev-page">
    <header className="ev-intro" data-evidence-reveal>
      <div className="ev-kicker"><p className="eyebrow">The evidence / 03</p><span className="ev-stamp">PHASE 7 · PRESERVED RESULT</span></div>
      <h1 className="ev-headline">The simplest<br />estimate <em>won.</em></h1>
      <div className="ev-intro-bottom"><p className="lede">A reasoning agent read the risk history. A one-line baseline kept the latest estimate. On this benchmark, the baseline performed better.</p><a href="#complete-results" className="ev-text-link">Examine all six approaches <span aria-hidden="true">↘</span></a></div>
    </header>

    <section className="ev-comparison" aria-labelledby="comparison-heading" data-evidence-reveal>
      <div className="ev-verdict"><span className="eyebrow">Agent loss / baseline loss</span><div className="ev-ratio">{ratio.toFixed(2)}<span>×</span></div><h2 id="comparison-heading">More loss.<br />No measured advantage.</h2><p>The agent’s benchmark loss was {ratio.toFixed(2)} times the baseline’s. This is a ratio of evaluation scores, not collision probabilities.</p><span className="ev-rule-label">NEGATIVE RESULTS ARE RESULTS.</span></div>
      <div className="ev-comparison-chart" ref={comparison}>
        <div className="ev-chart-heading"><span className="eyebrow">Two approaches. Same test set.</span><div className="ev-measure-switch" role="group" aria-label="Comparison measure"><button aria-pressed={measure === "loss"} onClick={() => setMeasure("loss")}>Loss ↓</button><button aria-pressed={measure === "recall"} onClick={() => setMeasure("recall")}>Recall ↑</button></div></div>
        {[baseline, agent].map((arm) => {
          const value = measure === "loss" ? arm.L : (arm.recall ?? 0);
          return <div key={arm.key} className={`ev-comparison-row ${arm.is_agent ? "ev-agent" : "ev-baseline"}`}>
            <div className="ev-comparison-label"><span>{arm.is_baseline ? "Latest-report baseline" : "LLM reasoning agent"}<small>{arm.is_baseline ? "Use the last visible risk estimate" : "Read the history and revise the estimate"}</small></span><strong aria-live="polite">{measure === "loss" ? value.toFixed(4) : `${(value * 100).toFixed(1)}%`}</strong></div>
            <div className="ev-comparison-track" role="img" aria-label={`${arm.label}: ${measure === "loss" ? `loss ${value.toFixed(4)}` : `recall ${(value * 100).toFixed(1)} percent`}`}><div className="ev-comparison-fill" style={{ width: `${100 * value / maxComparison}%` }} /></div>
          </div>;
        })}
        <p className="ev-chart-caption" aria-live="polite">{measure === "loss" ? "Linear scale from zero. Shorter is better. Loss combines high-risk prediction error with detection performance." : "Linear scale from 0 to 100%. Longer is better. Recall is the share of final high-risk labels the method identified."}</p>
        <div className="ev-sample-strip"><span><strong>{data.test_events.toLocaleString()}</strong> test events</span><span><strong>{data.test_high_risk.toLocaleString()}</strong> final high-risk labels</span><span><strong>≥ 2 days</strong> input cutoff before TCA</span></div>
      </div>
    </section>

    <section className="ev-reading" data-evidence-reveal aria-labelledby="reading-heading">
      <div><p className="eyebrow">Before reading a score</p><h2 id="reading-heading">A loss score<br />isn’t a risk.</h2></div>
      <div className="ev-reading-copy"><p>The model predicts <strong>log₁₀(P<sub>c</sub>)</strong>, where P<sub>c</sub> is a calculated probability of collision. An estimate of −5 means 1 in 100,000. Moving one unit higher multiplies that probability by ten.</p><p>The benchmark then scores those estimates using <strong>L = MSE<sub>HR</sub> / F₂</strong>. Lower loss is better. The score penalises inaccurate estimates on final high-risk labels and poor detection of those labels.</p><details className="ev-details"><summary>The definitions behind each column</summary><dl className="ev-definitions"><dt>MSE<sub>HR</sub> ↓</dt><dd>Mean squared error in log-risk, calculated on events whose final log-risk is at least −6.</dd><dt>F₂ ↑</dt><dd>A detection score that gives recall more weight than precision. It falls when a method misses high-risk labels.</dd><dt>Precision ↑</dt><dd>Of the events labelled high-risk by the method, the fraction with a final high-risk label.</dd><dt>Recall ↑</dt><dd>Of all final high-risk labels, the fraction detected by the method.</dd></dl></details><p className="ev-fine">“High-risk” means a final calculated log-risk ≥ −6 in Kelvins. It does not mean an observed collision. The agent’s invocation threshold of −7 is a separate rule.</p></div>
    </section>

    <section id="complete-results" className="ev-results" aria-labelledby="results-heading" data-evidence-reveal>
      <div className="ev-section-top"><div><p className="eyebrow">The full comparison</p><h2 id="results-heading">Every approach.<br />Same standard.</h2></div><p>All {data.arms.length} evaluated approaches, ordered by loss.<br /><span className="mono">↓ lower is better · ↑ higher is better</span></p></div>
      <div className="ev-table-wrap" tabIndex={0} role="region" aria-label="All evaluated approaches, scroll horizontally on small screens"><table className="ev-results-table"><caption>Original Phase 7 scores on {data.test_events.toLocaleString()} held-out events</caption><thead><tr><th scope="col">Approach</th><th scope="col">Loss L ↓</th><th scope="col">MSE<sub>HR</sub> ↓</th><th scope="col">F₂ ↑</th><th scope="col">Precision ↑</th><th scope="col">Recall ↑</th></tr></thead><tbody>{ordered.map((arm, index) => <tr key={arm.key} className={arm.is_baseline ? "ev-baseline-row" : arm.is_agent ? "ev-agent-row" : ""}><th scope="row"><span className="ev-rank">{String(index + 1).padStart(2, "0")}</span><span>{arm.label}<small>{arm.description}</small></span></th><td><strong>{number(arm.L)}</strong></td><td>{number(arm.mse_hr)}</td><td>{number(arm.f2)}</td><td>{number(arm.precision, 3)}</td><td>{number(arm.recall, 3)}</td></tr>)}</tbody></table></div>
      <p className="ev-fine">The baseline is highlighted in olive; the agent in rust. These are the stored original Phase 7 results, associated with the frozen code and evaluation protocol. This page reads that export; it does not run a new evaluation.</p>
    </section>

    <section className="ev-confidence" aria-labelledby="confidence-heading" data-evidence-reveal>
      <div className="ev-confidence-main"><p className="eyebrow">How stable was this comparison?</p><h2 id="confidence-heading">{(paired.fraction_favouring_agent * 100).toFixed(1)}%<span>of resamples<br />favoured the agent.</span></h2><p>In {paired.resamples.toLocaleString()} paired bootstrap resamples of these test events, none produced a lower loss for the agent.</p><p className="ev-fine">This describes sampling uncertainty within one test set. It does not measure variation across different dataset splits or repeated LLM runs.</p></div>
      <div className="ev-confidence-detail"><span className="eyebrow">Difference in loss · agent − baseline</span><div className="ev-ci-number">+{paired.median_difference.toFixed(4)}</div><p>Median paired difference</p><div className="ev-interval"><span>95% interval</span><strong>[+{paired.ci_low.toFixed(4)}, +{paired.ci_high.toFixed(4)}]</strong></div><p className="ev-fine">The full interval is above zero: the agent’s loss was higher. The bootstrap median need not equal the difference between the two original scores.</p></div>
    </section>

    <section className="ev-context" data-evidence-reveal aria-labelledby="published-heading"><div><p className="eyebrow">An external point of reference</p><h2 id="published-heading">The published<br />challenge record.</h2><p>Our latest-risk baseline reproduces the published LRP score to four decimal places. The constant −5 baseline agrees with CRP to three significant figures.</p><p className="ev-fine">The leaderboard is contextual. These published methods were not rerun by this project.</p></div><div className="ev-table-wrap" tabIndex={0} role="region" aria-label="Published challenge leaderboard excerpt"><table className="ev-leaderboard"><caption>Published reference scores · Table 3</caption><thead><tr><th scope="col">Published method</th><th scope="col">L ↓</th><th scope="col">MSE<sub>HR</sub> ↓</th><th scope="col">F₂ ↑</th></tr></thead><tbody>{Object.entries(data.published_leaderboard).map(([name, score]) => <tr key={name}><th scope="row">{leaderboardNames[name] ?? name}</th><td>{number(score.L, 3)}</td><td>{number(score.mse_hr, 3)}</td><td>{number(score.f2, 3)}</td></tr>)}</tbody></table><p className="ev-fine">Source: <a href="https://arxiv.org/abs/2008.03069" target="_blank" rel="noreferrer">{data.published_source} ↗</a></p></div></section>

    <footer className="ev-record" data-evidence-reveal><p className="eyebrow">The record stays visible</p><details className="ev-details"><summary>Provenance, boundaries &amp; reproducibility</summary><p>{data.provenance}</p><p>The export comes from <code>processed/test_results.json</code>. The original Phase 7 manifest was committed before scoring. Later exploratory prompt work is reported separately and does not overwrite this result.</p><dl className="ev-definitions"><dt>Dataset</dt><dd>ESA Kelvins collision-avoidance challenge; anonymised encounter histories.</dd><dt>Manifest commit</dt><dd><code>{data.frozen_manifest_head}</code></dd><dt>Primary agent</dt><dd>Prompt v1; used for visible log-risk ≥ −7. Below that threshold, the latest-report baseline stands.</dd><dt>Interpretation</dt><dd>Numerical risk estimates and benchmark labels, with no observed collision outcomes. Model reasoning is not an independently verified physical explanation.</dd></dl></details><div className="ev-next"><span>Follow the numbers back to their geometry.</span><Link href="/observatory" className="button button-dark">Open the observatory <span aria-hidden="true">↗</span></Link></div></footer>
  </article>;
}
