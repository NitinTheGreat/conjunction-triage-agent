"use client";

import { useSyncExternalStore } from "react";

function preference() {
  try {
    const choice = localStorage.getItem("conjunction-motion");
    if (choice) return choice === "full";
  } catch { /* A private browser can still use the system preference. */ }
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function subscribe(notify: () => void) {
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  media.addEventListener("change", notify);
  window.addEventListener("conjunction-motion", notify);
  window.addEventListener("storage", notify);
  return () => {
    media.removeEventListener("change", notify);
    window.removeEventListener("conjunction-motion", notify);
    window.removeEventListener("storage", notify);
  };
}

export function useMotion() {
  const enabled = useSyncExternalStore(subscribe, preference, () => false);
  const toggle = () => {
    const next = !preference();
    try { localStorage.setItem("conjunction-motion", next ? "full" : "reduced"); } catch { /* System preference remains available. */ }
    window.dispatchEvent(new Event("conjunction-motion"));
  };
  return { enabled, toggle };
}
