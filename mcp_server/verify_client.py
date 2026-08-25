"""Verify the MCP server with a real client over stdio.

Not a test double. This spawns ``python -m mcp_server.server`` as a subprocess, speaks the
actual protocol to it, lists the tools and calls three of them, then reports what came
back. If the handshake, the schemas or the calls are broken, this is where it shows —
importing the module and calling the functions directly would not exercise any of it.

``triage_events`` is listed but not called: it would cost money, and its offline paths are
covered in ``tests/test_mcp_server.py``.

    python -m mcp_server.verify_client
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

EXPECTED_TOOLS = {
    "fetch_conjunctions",
    "compute_pc",
    "get_object_metadata",
    "triage_events",
}

#: Units that must appear in each tool's description. A model choosing arguments sees only
#: this text, so a missing unit is a real defect rather than a documentation nicety.
REQUIRED_MENTIONS = {
    "fetch_conjunctions": ["km", "km/s", "metres", "floor"],
    "compute_pc": ["km^2", "METRES", "J2000/ECI", "covariance_frame"],
    "get_object_metadata": ["metres", "censored"],
    "triage_events": ["LOST", "baseline_risk", "-7.0"],
}


def _payload(result: Any) -> dict[str, Any]:
    """Pull the structured JSON out of a tool result."""
    if getattr(result, "structured_content", None):
        return result.structured_content
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    raise AssertionError("tool returned no readable content")


async def run() -> int:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
        cwd=str(REPO_ROOT),
    )

    failures: list[str] = []

    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print(f"connected to {init.server_info.name} v{init.server_info.version}")
            if init.instructions and "censored" in init.instructions:
                print("  instructions carry the censoring warning")
            else:
                failures.append("server instructions do not mention censoring")

            listing = await session.list_tools()
            names = {tool.name for tool in listing.tools}
            print(f"\ntools: {sorted(names)}")
            if names != EXPECTED_TOOLS:
                failures.append(f"tool set is {sorted(names)}, expected {sorted(EXPECTED_TOOLS)}")

            for tool in listing.tools:
                missing = [
                    token for token in REQUIRED_MENTIONS.get(tool.name, [])
                    if token not in (tool.description or "")
                ]
                if missing:
                    failures.append(f"{tool.name} description omits {missing}")
                else:
                    print(f"  {tool.name}: description states its units and caveats")

            compute = next(t for t in listing.tools if t.name == "compute_pc")
            if "covariance_frame" not in (compute.input_schema.get("required") or []):
                failures.append("compute_pc does not require covariance_frame")
            else:
                print("  compute_pc requires covariance_frame with no default")

            # -- compute_pc ------------------------------------------------------------
            result = _payload(await session.call_tool("compute_pc", {
                "position1_km": [7000.0, 0.0, 0.0],
                "velocity1_kms": [0.0, 7.5, 0.0],
                "covariance1": [[0.01, 0, 0], [0, 4.0, 0], [0, 0, 0.02]],
                "hbr1_m": 5.0,
                "position2_km": [7000.0, 0.0, 0.4],
                "velocity2_kms": [0.0, 0.0, 7.5],
                "covariance2": [[0.02, 0, 0], [0, 9.0, 0], [0, 0, 0.03]],
                "hbr2_m": 3.0,
                "covariance_frame": "uvw",
            }))
            print(f"\ncompute_pc -> pc = {result['pc']:.6e}, "
                  f"miss = {result['miss_distance_km']} km")
            if not result.get("ok") or not 0 <= result["pc"] <= 1:
                failures.append(f"compute_pc returned {result}")

            # -- compute_pc, refusing a matrix that is not a covariance ----------------
            refusal = _payload(await session.call_tool("compute_pc", {
                "position1_km": [7000.0, 0.0, 0.0],
                "velocity1_kms": [0.0, 7.5, 0.0],
                "covariance1": [[-4.0, 0, 0], [0, 4.0, 0], [0, 0, 0.02]],
                "hbr1_m": 5.0,
                "position2_km": [7000.0, 0.0, 0.4],
                "velocity2_kms": [0.0, 0.0, 7.5],
                "covariance2": [[0.02, 0, 0], [0, 9.0, 0], [0, 0, 0.03]],
                "hbr2_m": 3.0,
                "covariance_frame": "uvw",
            }))
            if refusal.get("ok") is False and "not repairable" in refusal["error"]:
                print("compute_pc -> refused a non-covariance with a structured error")
            else:
                failures.append(f"compute_pc accepted a non-covariance: {refusal}")

            # -- fetch_conjunctions ----------------------------------------------------
            fetched = _payload(await session.call_tool("fetch_conjunctions", {
                "source": "sfsh", "limit": 3, "exclude_floored": True,
            }))
            if fetched.get("ok"):
                print(f"\nfetch_conjunctions -> {fetched['returned']} of "
                      f"{fetched['total_matching']:,} matching events")
                top = fetched["events"][0]
                print(f"  top: pc = {top['pc']:.3e}, miss = {top['miss_distance_km']} km, "
                      f"floored = {top['pc_is_floored']}")
                if any(event["pc_is_floored"] for event in fetched["events"]):
                    failures.append("exclude_floored=true returned censored events")
                catalog = top["object1"]["catalog_id"]
            else:
                print(f"\nfetch_conjunctions -> unavailable: {fetched['error']}")
                catalog = None

            # -- get_object_metadata ---------------------------------------------------
            if catalog:
                metadata = _payload(
                    await session.call_tool("get_object_metadata", {"catalog_id": catalog})
                )
                if metadata.get("ok"):
                    print(f"\nget_object_metadata({catalog}) -> "
                          f"hbr {metadata['hard_body_radius_m']} m, "
                          f"{metadata['events']} events "
                          f"({metadata['censored_events']} censored)")
                else:
                    failures.append(f"get_object_metadata failed: {metadata}")

                unknown = _payload(await session.call_tool(
                    "get_object_metadata", {"catalog_id": "000000000"}
                ))
                if unknown.get("ok") is False:
                    print("get_object_metadata -> unknown id returns a structured error")
                else:
                    failures.append("get_object_metadata invented data for an unknown id")

    print()
    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        print(f"\n{len(failures)} problem(s) found.")
        return 1
    print("MCP server verified against a live client.")
    return 0


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
