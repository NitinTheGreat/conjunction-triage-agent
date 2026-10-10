"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { ArrowUpRight, BookOpen, Menu, Pause, Play, X } from "lucide-react";
import gsap from "gsap";
import { useMotion } from "@/lib/motion";

const navigation = [
  ["/", "The story"],
  ["/observatory", "Observatory"],
  ["/laboratory", "Laboratory"],
  ["/evidence", "The evidence"],
];

const glossary = [
  ["Conjunction", "A predicted close approach between two space objects. Proximity is a reason to investigate; it does not by itself establish a collision."],
  ["Closest approach / TCA", "The time when the predicted positions are closest. Miss distance is their separation at that time. Each pair in the data view has its own TCA."],
  ["Collision probability / Pc", "A calculated probability, conditional on the positions, object sizes, and uncertainty model. For example, 10⁻⁴ equals 0.01%, or 1 in 10,000."],
  ["Covariance", "The size and direction of positional uncertainty, expressed as a matrix. It describes what we know about an object's position, not the object's physical size."],
  ["Hard-body radius", "A radius representing the physical extent of an object. The two radii are added to define the collision region in the probability calculation."],
  ["UVW and ECI", "UVW uses each object's local radial, along-track, and cross-track axes. ECI uses inertial axes. Local covariances must be rotated into a shared frame before they can be added."],
  ["Probability dilution", "In the dilution regime, increasing positional uncertainty can make calculated Pc smaller. A low probability can accompany poor knowledge; an unflagged covariance is not guaranteed accurate."],
  ["Censored / unavailable", "TraCSS values at the inferred 10⁻¹⁰ reporting floor are treated as bounds. An unavailable value has no reported probability. Neither means zero risk."],
  ["CDM / baseline", "A Conjunction Data Message is one report about an encounter. A series contains successive reports. The latest-CDM baseline keeps the most recent visible risk estimate."],
  ["Log-risk", "The base-10 logarithm of Pc. A value of −5 means Pc = 10⁻⁵. One unit higher means ten times the calculated probability. Kelvins clips negligible risk at −30."],
  ["Three different thresholds", "The scene uses Pc = 10⁻⁴ as a reference. The agent is invoked at latest log-risk ≥ −7. Evaluation labels final log-risk ≥ −6 high-risk. These are distinct benchmark definitions, not universal action rules."],
  ["Evaluation loss / L", "The Kelvins score is high-risk prediction error divided by F₂, a detection score that emphasizes recall. Lower loss is better. It measures benchmark performance, not actual collision outcomes."],
];

export function OrbitMark({ className = "" }: { className?: string }) {
  return <svg className={className} viewBox="0 0 44 44" fill="none" aria-hidden="true"><ellipse cx="22" cy="22" rx="20" ry="9" stroke="currentColor" strokeWidth="1.4" transform="rotate(-38 22 22)"/><ellipse cx="22" cy="22" rx="20" ry="9" stroke="currentColor" strokeWidth="1.4" transform="rotate(38 22 22)"/><circle cx="22" cy="22" r="4" fill="currentColor"/><circle cx="36" cy="8" r="2.5" fill="currentColor"/></svg>;
}

export default function SiteShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const guide = useRef<HTMLDialogElement>(null);
  const mobile = useRef<HTMLDialogElement>(null);
  const header = useRef<HTMLElement>(null);
  const { enabled, toggle } = useMotion();

  useEffect(() => {
    document.documentElement.dataset.motion = enabled ? "full" : "reduced";
  }, [enabled]);

  useEffect(() => {
    const node = header.current;
    if (!node || !enabled) return;
    const context = gsap.context(() => {
      gsap.fromTo(".nav-link.is-active .nav-dot", { scale: 0 }, { scale: 1, duration: .6, ease: "back.out(2)" });
    }, node);
    return () => context.revert();
  }, [pathname, enabled]);

  function openDialog(dialog: HTMLDialogElement | null) {
    if (!dialog || dialog.open) return;
    gsap.killTweensOf(dialog);
    gsap.set(dialog, { clearProps: "opacity,transform" });
    dialog.showModal();
    document.documentElement.style.overflow = "hidden";
    if (enabled) gsap.fromTo(dialog, { opacity: 0, y: 25, scale: .985 }, { opacity: 1, y: 0, scale: 1, duration: .45, ease: "power3.out" });
  }

  function closeDialog(dialog: HTMLDialogElement | null) {
    if (!dialog) return;
    gsap.killTweensOf(dialog);
    const done = () => {
      dialog.close();
      gsap.set(dialog, { clearProps: "opacity,transform" });
      document.documentElement.style.overflow = "";
    };
    if (enabled) gsap.to(dialog, { opacity: 0, y: 15, duration: .2, onComplete: done });
    else done();
  }

  return <>
    <a className="skip-link" href="#main">Skip to content</a>
    <header className="site-header" ref={header}>
      <Link href="/" className="brand" aria-label="ConjunctionTriage home"><OrbitMark className="brand-mark"/><span>conjunction<span className="brand-triage">triage</span><small>AN ORBITAL OBSERVATORY</small></span></Link>
      <nav className="desktop-nav" aria-label="Main navigation">{navigation.map(([href, label]) => <Link href={href} key={href} className={`nav-link ${pathname === href ? "is-active" : ""}`} aria-current={pathname === href ? "page" : undefined}><i className="nav-dot"/>{label}</Link>)}</nav>
      <div className="header-tools"><button className="guide-trigger" onClick={() => openDialog(guide.current)}><BookOpen size={14}/><span>Field guide</span></button><button className="icon-button mobile-menu-trigger" aria-label="Open navigation" onClick={() => openDialog(mobile.current)}><Menu size={20}/></button></div>
    </header>
    <main id="main" tabIndex={-1}>{children}</main>
    <footer className="site-footer">
      <div className="footer-top"><Link href="/" className="footer-brand"><OrbitMark/>There is more<br/>to a close approach.</Link><div className="footer-note"><span className="eyebrow">A QUESTION, TESTED.</span><p>Geometry. Uncertainty. Evidence.<br/>Built to make the reasoning visible.</p><Link href="/laboratory">Step inside the laboratory <ArrowUpRight size={16}/></Link></div></div>
      <div className="footer-bottom"><span>CONJUNCTIONTRIAGE © 2026</span><span>Historical benchmarks · Research use only</span><button className="motion-toggle" onClick={toggle} aria-pressed={!enabled}>{enabled ? <Pause size={12}/> : <Play size={12}/>} Motion {enabled ? "on" : "off"}</button></div>
    </footer>
    <dialog className="field-guide-dialog" ref={guide} onCancel={(event) => { event.preventDefault(); closeDialog(guide.current); }} onClose={() => { document.documentElement.style.overflow = ""; }}>
      <div className="guide-heading"><div><p className="eyebrow">THE SMALL PRINT, MADE READABLE</p><h2>A field guide<br/>to <em>orbital risk.</em></h2></div><button className="icon-button" aria-label="Close field guide" onClick={() => closeDialog(guide.current)}><X/></button></div>
      <p className="guide-lede">You do not need an orbital mechanics background. These are the ideas behind the numbers.</p>
      <dl className="glossary">{glossary.map(([term, definition], index) => <div key={term}><dt><span>{String(index + 1).padStart(2, "0")}</span>{term}</dt><dd>{definition}</dd></div>)}</dl>
      <div className="notice">The animated landing scene is a conceptual illustration. The observatory shows exported historical positions. TraCSS geometry and anonymised Kelvins risk histories are separate datasets.</div>
    </dialog>
    <dialog className="mobile-nav-dialog" ref={mobile} onCancel={(event) => { event.preventDefault(); closeDialog(mobile.current); }} onClose={() => { document.documentElement.style.overflow = ""; }}><div className="mobile-nav-top"><span className="eyebrow">EXPLORE THE OBSERVATORY</span><button className="icon-button" aria-label="Close navigation" onClick={() => closeDialog(mobile.current)}><X/></button></div><nav aria-label="Mobile navigation">{navigation.map(([href, label], i) => <Link href={href} key={href} onClick={() => closeDialog(mobile.current)}><span>0{i + 1}</span>{label}<ArrowUpRight/></Link>)}</nav><p className="muted">Space safety, with the evidence in view.</p></dialog>
  </>;
}
