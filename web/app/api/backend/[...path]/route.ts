import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const paths: Record<string, string[]> = { GET: ["health", "events"], POST: ["pc", "triage", "screen"] };

async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const endpoint = (await context.params).path.join("/");
  if (!paths[request.method]?.includes(endpoint)) return NextResponse.json({ detail: "Unknown research endpoint." }, { status: 404 });
  const origin = request.headers.get("origin");
  if (request.method === "POST" && origin) {
    try {
      if (new URL(origin).host !== request.headers.get("host")) throw new Error("Origin mismatch");
    } catch {
      return NextResponse.json({ detail: "Requests must originate from this workspace." }, { status: 403 });
    }
  }
  const base = process.env.ORBITAL_API_URL || "http://127.0.0.1:8000";
  let body: string | undefined;
  if (request.method === "POST") {
    if (Number(request.headers.get("content-length") || 0) > 65536) return NextResponse.json({ detail: "Request is too large." }, { status: 413 });
    body = await request.text();
    if (new TextEncoder().encode(body).byteLength > 65536) return NextResponse.json({ detail: "Request is too large." }, { status: 413 });
  }
  try {
    const response = await fetch(`${base.replace(/\/$/, "")}/${endpoint}${request.nextUrl.search}`, {
      method: request.method,
      headers: { "Content-Type": "application/json" },
      body,
      signal: AbortSignal.timeout(endpoint === "triage" ? 180_000 : 20_000),
      cache: "no-store",
    });
    const payload = await response.json();
    return NextResponse.json(payload, { status: response.status, headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "service_unavailable", detail: "The physics API is unavailable. Start the Python API on port 8000, then reconnect. Recorded examples and stored results remain available." }, { status: 503 });
  }
}

export { forward as GET, forward as POST };
