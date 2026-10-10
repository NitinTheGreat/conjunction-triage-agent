import Link from "next/link";
export default function NotFound() {
  return <div className="page-shell not-found"><p className="eyebrow">404 / OUT OF ORBIT</p><h1 className="page-title">Let’s find our<br/><em>way back.</em></h1><p className="lede">This route is outside the observatory.</p><Link className="button button-dark" href="/">Return to the story ↗</Link></div>;
}
