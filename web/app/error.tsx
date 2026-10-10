"use client";
export default function Error({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <div className="page-shell not-found"><p className="eyebrow">A MOMENTARY INTERRUPTION</p><h1 className="page-title">Let’s try<br/><em>that again.</em></h1><p className="lede">This workspace could not load. Your underlying benchmark data have not changed.</p><button className="button button-dark" onClick={reset}>Reload this workspace ↗</button></div>;
}
