"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import { useRef } from "react";
import { ArrowDown, ArrowDownRight, ArrowRight, ArrowUpRight, MoveUpRight } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { useMotion } from "@/lib/motion";
import "./home.css";

gsap.registerPlugin(useGSAP, ScrollTrigger);
const PlanetScene = dynamic(() => import("@/components/planet-scene"), { ssr: false, loading: () => <div className="planet-loading"><span/><p>ASSEMBLING THE ORBITS</p></div> });

const chapters = [
  { n: "01", title: "First, the distance.", detail: "Two objects. One close approach. Miss distance tells you how close their predicted positions come. It is where the investigation starts.", word: "PROXIMITY" },
  { n: "02", title: "Then, what we don’t know.", detail: "Positions are estimates. Each has an uncertainty region. Its size and direction can change the collision probability, even when the distance stays the same.", word: "UNCERTAINTY" },
  { n: "03", title: "Finally, the evidence.", detail: "A convincing explanation is still a hypothesis. We compare the agent’s estimate with a simple baseline, using the same held-out events and a defined score.", word: "EVALUATION" },
];

export default function HomeExperience() {
  const root = useRef<HTMLDivElement>(null);
  const { enabled } = useMotion();

  useGSAP(() => {
    if (!enabled) return;
    const intro = gsap.timeline({ defaults: { ease: "power3.out" } });
    intro.from(".hero-kicker", { y: 12, autoAlpha: 0, duration: .7 }, .1)
      .from(".hero-line > span", { yPercent: 110, rotate: 3, duration: 1.1, stagger: .12 }, .2)
      .from(".hero-description, .hero-actions, .hero-bottom-note", { y: 22, autoAlpha: 0, duration: .8, stagger: .1 }, .55)
      .from(".hero-planet-wrap", { scale: .88, autoAlpha: 0, duration: 1.4 }, .2)
      .from(".hero-marginalia, .hero-bottom", { autoAlpha: 0, duration: .8 }, .8);

    gsap.to(".hero-planet-wrap", { y: 70, rotation: 5, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 1 } });
    gsap.to(".hero-scroll-arrow", { y: 7, repeat: -1, yoyo: true, duration: 1.3, ease: "sine.inOut" });

    gsap.utils.toArray<HTMLElement>("[data-reveal]").forEach((element) => {
      gsap.from(element, { autoAlpha: 0, y: 38, duration: .85, ease: "power3.out", scrollTrigger: { trigger: element, start: "top 90%", once: true } });
    });
    const counters = gsap.utils.toArray<HTMLElement>("[data-counter]");
    counters.forEach((element) => {
      const end = Number(element.dataset.counter);
      const value = { number: 0 };
      gsap.to(value, { number: end, duration: 1.7, ease: "power2.out", onUpdate: () => { element.textContent = Math.round(value.number).toLocaleString("en-US"); }, scrollTrigger: { trigger: element, start: "top 95%", once: true } });
    });

    const timeline = gsap.timeline({ scrollTrigger: { trigger: ".story-section", start: "top 35%", end: "bottom 75%", scrub: 1 } });
    timeline.fromTo(".story-object-a", { x: -95, y: -45 }, { x: 0, y: 0, duration: 1 })
      .fromTo(".story-object-b", { x: 95, y: 45 }, { x: 0, y: 0, duration: 1 }, 0)
      .fromTo(".story-uncertainty", { scale: .1, autoAlpha: 0, transformOrigin: "center" }, { scale: 1, autoAlpha: .9, duration: 1 }, .8)
      .fromTo(".story-crosshair", { autoAlpha: 0, rotation: -40, transformOrigin: "center" }, { autoAlpha: 1, rotation: 0, duration: 1 }, 1.7);
    gsap.from(".finding-bar-fill", { scaleX: 0, transformOrigin: "left", duration: 1.4, stagger: .2, ease: "power3.out", scrollTrigger: { trigger: ".finding-bars", start: "top 85%", once: true } });
    return () => {
      // Cancelling an entrance animation must never leave a partial dataset count.
      counters.forEach((element) => { element.textContent = Number(element.dataset.counter).toLocaleString("en-US"); });
    };
  }, { scope: root, dependencies: [enabled], revertOnUpdate: true });

  return <div ref={root} className="home-experience">
    <section className="hero">
      <div className="hero-topline"><p className="hero-kicker eyebrow"><i/> THE SCIENCE OF GETTING CLOSE</p><span className="mono hero-edition">RESEARCH EDITION — 001</span></div>
      <div className="hero-main">
        <div className="hero-copy"><h1><span className="hero-line"><span>A matter</span></span><span className="hero-line"><span>of <em>space.</em></span></span></h1><p className="hero-description">Out there, a few kilometres can raise a thousand questions. Explore what a close approach means—and what it takes to understand the risk.</p><div className="hero-actions"><Link className="button button-dark hero-cta" href="/observatory">Enter the observatory <ArrowUpRight size={18}/></Link><a className="story-link" href="#the-question">Discover the science <ArrowDown size={15}/></a></div><p className="hero-bottom-note mono">REAL BENCHMARKS. OPEN QUESTIONS. VISIBLE EVIDENCE.</p></div>
        <div className="hero-planet-wrap"><PlanetScene variant="hero" paused={!enabled} className="hero-planet"/><span className="planet-caption mono">FIG. 01 — AN ENCOUNTER IN MOTION</span></div>
        <div className="hero-marginalia"><span className="mono">EARTH-CENTRED<br/>HUMAN-UNDERSTANDABLE</span><i/><span className="mono">CONCEPTUAL ORBITS<br/>NOT LIVE TRACKING</span></div>
      </div>
      <div className="hero-bottom"><a href="#the-question" className="scroll-invite"><span className="hero-scroll-arrow"><ArrowDown size={18}/></span><span className="mono">SCROLL TO GET CLOSER</span></a><div className="hero-legend mono"><span><i className="legend-seed olive"/>POSITION</span><span><i className="legend-seed rust"/>UNCERTAINTY</span><span className="drag-hint">DRAG THE GLOBE TO EXPLORE ↗</span></div></div>
    </section>

    <section className="scope-strip" aria-label="Project scope"><div data-reveal><span className="mono">THE SCALE OF THE QUESTION</span><ArrowDownRight size={30}/></div><div><strong data-counter="1196860">1,196,860</strong><span>ingested TraCSS records</span></div><div><strong data-counter="2000">2,000</strong><span>encounters to explore</span></div><div><strong data-counter="2167">2,167</strong><span>held-out evaluation events</span></div></section>

    <section className="story-section" id="the-question">
      <div className="story-heading" data-reveal><p className="eyebrow">01 / ASK A BETTER QUESTION</p><h2>How close is<br/><em>too close?</em></h2><p>A distance tells you where to look.<br/>Understanding risk takes another dimension.</p></div>
      <div className="story-layout">
        <div className="story-diagram"><div className="diagram-top mono"><span>THE ANATOMY OF AN ENCOUNTER</span><span>FIG. 02</span></div><svg viewBox="0 0 580 480" role="img" aria-label="Conceptual diagram of two object positions and their uncertainty regions at close approach"><defs><pattern id="story-grid" width="32" height="32" patternUnits="userSpaceOnUse"><path d="M32 0H0V32" fill="none" stroke="#d0d68b" strokeOpacity=".08"/></pattern></defs><rect width="580" height="480" fill="url(#story-grid)"/><g fill="none"><path d="M-20 340Q190 360 600 105" stroke="#d0d68b" strokeWidth="1.2"/><path d="M-20 115Q255 110 600 355" stroke="#c68468" strokeWidth="1.2" strokeDasharray="5 5"/><g className="story-object-a"><ellipse className="story-uncertainty" cx="267" cy="235" rx="107" ry="48" transform="rotate(-20 267 235)" fill="#d0d68b" fillOpacity=".1" stroke="#d0d68b" strokeDasharray="3 4"/><circle cx="267" cy="235" r="7" fill="#d0d68b"/><circle cx="267" cy="235" r="14" stroke="#d0d68b" strokeOpacity=".35"/></g><g className="story-object-b"><ellipse className="story-uncertainty" cx="330" cy="265" rx="95" ry="40" transform="rotate(23 330 265)" fill="#c68468" fillOpacity=".1" stroke="#c68468" strokeDasharray="3 4"/><circle cx="330" cy="265" r="6" fill="#c68468"/></g><path d="M267 254l52 25" stroke="#f1ecdb" strokeWidth=".7"/><g className="story-crosshair" stroke="#e8e4da" strokeOpacity=".5"><circle cx="298" cy="250" r="140" strokeDasharray="2 7"/><path d="M298 96v23M298 381v23M144 250h23M429 250h23"/></g></g><text x="169" y="170" fill="#d0d68b" fontSize="10" fontFamily="monospace">OBJECT A</text><text x="363" y="312" fill="#c68468" fontSize="10" fontFamily="monospace">OBJECT B</text><text x="217" y="421" fill="#b4b5a3" fontSize="10" fontFamily="monospace">UNCERTAINTY IS PART OF THE PICTURE</text></svg><div className="diagram-bottom mono"><span>ILLUSTRATIVE GEOMETRY</span><span>NOT TO SCALE</span></div></div>
        <div className="story-chapters">{chapters.map((chapter) => <article className="story-chapter" key={chapter.n} data-reveal><span className="chapter-number">{chapter.n}</span><div><span className="eyebrow">{chapter.word}</span><h3>{chapter.title}</h3><p>{chapter.detail}</p></div></article>)}</div>
      </div>
    </section>

    <section className="workspace-section">
      <div className="section-heading" data-reveal><div><p className="eyebrow">02 / FOLLOW YOUR CURIOSITY</p><h2>Three ways<br/>to <em>look closer.</em></h2></div><p>Go from an encounter in orbit to a calculation you can change, then to a result you can question.</p></div>
      <div className="workspace-list">
        <Link href="/observatory" className="workspace-row" data-reveal><span className="workspace-number mono">01 /</span><div className="workspace-row-title"><h3>The observatory</h3><span className="mono">GEOMETRY + DISTRIBUTIONS</span></div><p>Rotate the Earth. Pick a pair. Explore how one encounter fits into the full dataset.</p><div className="workspace-mini mini-orbit" aria-hidden="true"><i/><i/><span/></div><span className="round-arrow"><ArrowUpRight/></span></Link>
        <Link href="/laboratory" className="workspace-row" data-reveal><span className="workspace-number mono">02 /</span><div className="workspace-row-title"><h3>The laboratory</h3><span className="mono">PHYSICS + REASONING</span></div><p>Change the assumptions. Compute a probability. Inspect the reasoning behind an agent’s estimate.</p><div className="workspace-mini mini-wave" aria-hidden="true"><svg viewBox="0 0 130 60"><path d="M0 55Q24 55 41 20T65 35T86 20T130 55" fill="none" stroke="currentColor"/><path d="M0 55Q34 55 50 12T83 28T130 55" fill="none" stroke="currentColor" opacity=".4"/></svg></div><span className="round-arrow"><ArrowUpRight/></span></Link>
        <Link href="/evidence" className="workspace-row" data-reveal><span className="workspace-number mono">03 /</span><div className="workspace-row-title"><h3>The evidence</h3><span className="mono">SIX METHODS. ONE TEST.</span></div><p>Inspect the original held-out evaluation, the baseline comparison, and the limits of the finding.</p><div className="workspace-mini mini-bars" aria-hidden="true"><i/><i/><i/><i/><i/></div><span className="round-arrow"><ArrowUpRight/></span></Link>
      </div>
    </section>

    <section className="finding-section">
      <div className="finding-copy" data-reveal><p className="eyebrow">03 / THE FINDING THAT MATTERS</p><h2>The simpler<br/>answer <em>won.</em></h2><p>The reasoning agent produced detailed explanations. The latest-message baseline produced the better score. Testing both is what makes the project useful.</p><Link className="button button-dark" href="/evidence">Examine the evidence <ArrowUpRight size={17}/></Link></div>
      <div className="finding-bars" data-reveal><span className="mono finding-metric-label">OFFICIAL KELVINS LOSS · LOWER IS BETTER</span><div className="finding-bar-item"><div><span>Latest-CDM baseline</span><strong>0.6940</strong></div><div className="finding-bar-track"><div className="finding-bar-fill baseline" style={{ width: "41.79%" }}/></div><p>Keep the most recent visible risk.</p></div><div className="finding-bar-item"><div><span>LLM reasoning agent</span><strong>1.6606</strong></div><div className="finding-bar-track"><div className="finding-bar-fill agent"/></div><p>About 2.4× the baseline’s loss.</p></div><div className="finding-footnote"><MoveUpRight size={20}/><span>2,167 held-out events. Original Phase 7 evaluation.<br/>Calculated risk labels, not observed collisions.</span></div></div>
    </section>

    <section className="closing-section" data-reveal><span className="eyebrow">A WORKING SYSTEM. AN OPEN QUESTION.</span><h2>Understanding starts<br/>with <em>looking closer.</em></h2><Link href="/observatory" className="closing-link">Let’s explore <ArrowRight size={38}/></Link><p>Historical data. Reproducible methods. Room to question the result.</p></section>
  </div>;
}
