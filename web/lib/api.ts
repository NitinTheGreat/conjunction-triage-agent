"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { HealthResponse } from "./types";

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), path.startsWith("/triage") ? 185_000 : 30_000);
  const abort = () => controller.abort();
  options.signal?.addEventListener("abort", abort, { once: true });
  if (options.signal?.aborted) controller.abort();
  try {
    const response = await fetch(`/api/backend${path}`, {
      ...options,
      headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...options.headers },
      signal: controller.signal,
      cache: "no-store",
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "The request could not be completed.");
    return payload as T;
  } catch (error) {
    if (controller.signal.aborted) throw new Error("The request timed out or was cancelled. The server may still be processing it.");
    if (error instanceof TypeError) throw new Error("The service could not be reached. Check the connection and try again.");
    throw error;
  } finally {
    clearTimeout(timeout);
    options.signal?.removeEventListener("abort", abort);
  }
}

export function useServiceHealth() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<"checking" | "online" | "offline">("checking");
  const pending = useRef<AbortController | null>(null);
  const refresh = useCallback(() => {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setStatus("checking");
    apiRequest<HealthResponse>("/health", { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return;
        if (!result.checks?.sgp4 || !result.checks?.tracss_store) throw new Error("Unexpected service");
        setHealth(result);
        setStatus("online");
      })
      .catch(() => {
        if (controller.signal.aborted) return;
        setHealth(null);
        setStatus("offline");
      });
  }, []);
  useEffect(() => {
    const timer = setTimeout(refresh, 0);
    return () => { clearTimeout(timer); pending.current?.abort(); };
  }, [refresh]);
  return { health, status, refresh };
}
