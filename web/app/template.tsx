"use client";

import { useRef } from "react";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { useMotion } from "@/lib/motion";

gsap.registerPlugin(useGSAP);

export default function Template({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const { enabled } = useMotion();
  useGSAP(() => {
    if (!enabled) return;
    gsap.fromTo(ref.current, { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: .55, ease: "power2.out", clearProps: "all" });
  }, { scope: ref, dependencies: [enabled], revertOnUpdate: true });
  return <div ref={ref} className="route-content">{children}</div>;
}
